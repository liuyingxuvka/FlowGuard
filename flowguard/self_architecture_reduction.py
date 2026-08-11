"""Read-only architecture-reduction audit bound to FlowGuard's self blueprint."""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from .architecture_reduction import (
    CANDIDATE_COLLAPSE_ADAPTER,
    CANDIDATE_KEEP_PUBLIC_FACADE,
    CANDIDATE_MANUAL_REVIEW,
    CANDIDATE_MERGE_HANDLERS,
    CANDIDATE_MERGE_MODULES,
    CANDIDATE_REMOVE_BRANCH,
    CANDIDATE_REMOVE_DUPLICATE_VALIDATION,
    COMPATIBILITY_ACTION_KEEP,
    COMPATIBILITY_ACTION_PRUNE,
    COMPATIBILITY_SURFACE_CURRENT_CONTRACT,
    COMPATIBILITY_SURFACE_PRUNE_CANDIDATE,
    PROOF_RISKY_KEEP,
    PROOF_SAFE_BY_EQUIVALENCE,
    PROOF_SAFE_BY_PUBLIC_FACADE,
    ROUTE_DEVELOPMENT_PROCESS_FLOW,
    ROUTE_MODEL_TEST_ALIGNMENT,
    ROUTE_STRUCTURE_MESH,
    STEP_ACTION_DELEGATE,
    STEP_ACTION_MERGE,
    STEP_ACTION_REMOVE,
    STEP_ACTION_RETAIN,
    STEP_ACTION_UNRESOLVED,
    STEP_KIND_ADAPTER,
    STEP_KIND_BRANCH,
    STEP_KIND_BUILDER,
    STEP_KIND_HELPER,
    STEP_KIND_MODULE_BOUNDARY,
    STEP_KIND_OTHER,
    STEP_KIND_ROUTE_DISPATCH,
    STEP_KIND_SERIALIZATION,
    STEP_KIND_VALIDATION,
    TARGET_ACTION_COLLAPSE,
    TARGET_ACTION_KEEP_FACADE,
    TARGET_ACTION_MANUAL_REVIEW,
    TARGET_ACTION_MERGE,
    TARGET_ACTION_REMOVE,
    ArchitectureReductionCandidate,
    ArchitectureReductionPlan,
    ArchitectureReductionReport,
    ArchitectureReductionStepAssessment,
    ArchitectureReductionStepCost,
    ArchitectureReductionTrigger,
    CompatibilitySurfaceClassification,
    ObservableArchitectureContract,
    review_architecture_reduction,
)
from .behavior_commitment import (
    BCL_DISPOSITION_MODELED,
    BCL_MODEL_SYNC_OWNER_CURRENT,
    BCL_SOURCE_AUTHORITY_NORMATIVE,
    BCL_SOURCE_AUTHORITY_OBSERVED,
    behavior_commitment_ledger_fingerprint,
    load_behavior_commitment_ledger,
    review_behavior_commitment_ledger,
)
from .evidence_receipts import (
    EvidenceReceipt,
    RECEIPT_STATUS_PASS,
    ReceiptVerificationResult,
    fingerprint_value,
    list_evidence_receipts,
    load_evidence_receipt,
    receipt_path,
    verify_evidence_receipt,
)
from .self_blueprint import (
    FlowGuardSelfBlueprintBundle,
    SelfBlueprintBuildInputIdentity,
    build_flowguard_self_blueprint,
    capture_flowguard_self_blueprint_build_input_identity,
)
from .project_blueprint import (
    _CanonicalConsumerIndex,
    _canonical_consumer_index,
)
from .self_reduction_inventory import (
    SELF_REDUCTION_DISPOSITIONS,
    SelfReductionCandidateBinding,
    SelfReductionRetainDisposition,
    SelfReductionUniverse,
    derive_self_reduction_retain_dispositions,
    derive_self_reduction_universe,
)
from .validation_ownership import (
    OWNER_RECEIPT_KIND,
    OWNER_RECEIPT_SCOPE,
    ValidationOwnerContract,
    assert_validation_owner_receipt_integrity,
    build_owner_current,
    build_child_bound_owner_receipt_context,
    find_reusable_owner_receipt,
    save_child_bound_owner_receipt,
    topological_owner_contracts,
)
from .validation_owner_execution import (
    VALIDATION_OWNER_EXECUTION_SCHEMA,
    publish_supervised_validation_owner_result,
)
from .process_supervision import run_supervised


SELF_ARCHITECTURE_REDUCTION_SCHEMA = (
    "flowguard.self_architecture_reduction_review.v14"
)

SELF_REDUCTION_EVIDENCE_NEIGHBORHOOD_SCHEMA = (
    "flowguard.self_reduction_evidence_neighborhood.v1"
)
SELF_REDUCTION_EVIDENCE_NEIGHBORHOOD_CATALOG_SCHEMA = (
    "flowguard.self_reduction_evidence_neighborhood_catalog.v1"
)
SELF_REDUCTION_OBSERVABLE_CONTRACT_SCHEMA = (
    "flowguard.self_reduction_observable_contract.v2"
)
SELF_REDUCTION_CANDIDATE_INVENTORY_SCHEMA = (
    "flowguard.self_reduction_candidate_inventory.v5"
)
SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT = 8
_INLINE_EVIDENCE_NEIGHBORHOOD_FIELDS = frozenset(
    {
        "test_node_ids",
        "coverage_ids",
        "covered_dimensions",
        "current_test_receipt_ids",
    }
)

SELF_REDUCTION_PARITY_OBLIGATION_IDS = (
    "caller_consumer_parity",
    "error_parity",
    "side_effect_parity",
    "state_parity",
)
SELF_REDUCTION_TEST_CHILD_SCHEMA = "flowguard.self_reduction_test_child.v1"
SELF_REDUCTION_PARITY_CHILD_SCHEMA = "flowguard.self_reduction_parity_child.v1"
SELF_REDUCTION_AGGREGATE_SCHEMA = "flowguard.self_reduction_aggregate.v1"
SELF_REDUCTION_PROOF_RECORD_SCHEMA = (
    "flowguard.self_reduction_proof_record.v1"
)
SELF_REDUCTION_TEST_EXECUTION_SCHEMA = (
    "flowguard.self_reduction_pytest_execution.v1"
)
SELF_REDUCTION_PARITY_EXECUTION_SCHEMA = (
    "flowguard.self_reduction_behavior_parity_execution.v1"
)
_SELF_REDUCTION_RESULT_MARKER = "FLOWGUARD_SELF_REDUCTION_RESULT="
_CANONICAL_VALIDATION_OWNER_RELATIVE = Path(
    ".flowguard/evidence/validation-owners"
)
_BEHAVIOR_LEDGER_RELATIVE = Path(
    ".flowguard/behavior_commitment_ledger/ledger.json"
)


@dataclass(frozen=True)
class SelfReductionEvidenceNeighborhood:
    """One content-addressed coverage neighborhood shared by candidates."""

    test_node_ids: tuple[str, ...]
    coverage_ids: tuple[str, ...]
    covered_dimensions: tuple[str, ...]
    current_test_receipt_ids: tuple[str, ...]
    neighborhood_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "test_node_ids",
            "coverage_ids",
            "covered_dimensions",
            "current_test_receipt_ids",
        ):
            values = tuple(
                sorted(
                    {
                        str(value)
                        for value in getattr(self, name)
                        if str(value)
                    }
                )
            )
            object.__setattr__(self, name, values)
        fingerprint = fingerprint_value(self.identity_payload())
        object.__setattr__(self, "fingerprint", fingerprint)
        object.__setattr__(
            self,
            "neighborhood_id",
            "self-reduction-evidence-neighborhood:"
            + fingerprint.split(":", 1)[1],
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": SELF_REDUCTION_EVIDENCE_NEIGHBORHOOD_SCHEMA,
            "test_node_ids": list(self.test_node_ids),
            "coverage_ids": list(self.coverage_ids),
            "covered_dimensions": list(self.covered_dimensions),
            "current_test_receipt_ids": list(
                self.current_test_receipt_ids
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "neighborhood_id": self.neighborhood_id,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class SelfReductionEvidenceNeighborhoodCatalog:
    """The one direct-current catalog consumed by a self-reduction review."""

    entries: tuple[SelfReductionEvidenceNeighborhood, ...]
    fingerprint: str = field(init=False)
    _by_id: dict[str, SelfReductionEvidenceNeighborhood] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        supplied_entries = tuple(self.entries)
        if any(
            not isinstance(row, SelfReductionEvidenceNeighborhood)
            for row in supplied_entries
        ):
            raise TypeError(
                "self reduction evidence catalog requires typed entries"
            )
        entries = tuple(
            sorted(supplied_entries, key=lambda row: row.neighborhood_id)
        )
        ids = tuple(row.neighborhood_id for row in entries)
        if len(ids) != len(set(ids)):
            raise ValueError(
                "self reduction evidence catalog contains duplicate ids"
            )
        for row in entries:
            expected_fingerprint = fingerprint_value(row.identity_payload())
            expected_id = (
                "self-reduction-evidence-neighborhood:"
                + expected_fingerprint.split(":", 1)[1]
            )
            if (
                row.fingerprint != expected_fingerprint
                or row.neighborhood_id != expected_id
            ):
                raise ValueError(
                    "self reduction evidence neighborhood is not exact-current"
                )
        object.__setattr__(self, "entries", entries)
        object.__setattr__(
            self,
            "_by_id",
            {row.neighborhood_id: row for row in entries},
        )
        object.__setattr__(
            self,
            "fingerprint",
            fingerprint_value(self.identity_payload()),
        )

    @property
    def neighborhood_ids(self) -> tuple[str, ...]:
        return tuple(row.neighborhood_id for row in self.entries)

    def resolve(self, neighborhood_id: str) -> SelfReductionEvidenceNeighborhood:
        row = self._by_id.get(str(neighborhood_id))
        if row is None:
            raise ValueError(
                "self reduction candidate references an unknown evidence neighborhood"
            )
        return row

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": (
                SELF_REDUCTION_EVIDENCE_NEIGHBORHOOD_CATALOG_SCHEMA
            ),
            "entries": [row.to_dict() for row in self.entries],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "fingerprint": self.fingerprint,
        }


_PYTEST_PROOF_RUNNER_SOURCE = r'''import json
import base64
import contextlib
import io
import os
import sys

os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
import pytest

subject = json.loads(base64.urlsafe_b64decode(sys.argv[1]).decode("utf-8"))
requested = tuple(subject["pytest_nodeids"])
role = subject["role"]
records = {}
collected = []
deselected = []
executed_lines = {}
tracked_paths = {
    os.path.normcase(os.path.abspath(row["path"]))
    for row in (
        list(subject.get("runtime_surfaces", []))
        + list(subject.get("oracle_checks", []))
    )
}


class Plugin:
    def pytest_collection_modifyitems(self, session, config, items):
        collected.extend(item.nodeid for item in items)

    def pytest_deselected(self, items):
        deselected.extend(item.nodeid for item in items)

    def pytest_runtest_logreport(self, report):
        row = records.setdefault(report.nodeid, {})
        row[report.when] = report.outcome
        if hasattr(report, "wasxfail"):
            row["wasxfail"] = str(report.wasxfail)


def trace(frame, event, arg):
    path = os.path.normcase(os.path.abspath(frame.f_code.co_filename))
    if path not in tracked_paths:
        return None
    if event == "line":
        executed_lines.setdefault(path, set()).add(int(frame.f_lineno))
    return trace


captured_stdout = io.StringIO()
captured_stderr = io.StringIO()
with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
    if role == "parity":
        sys.settrace(trace)
    try:
        pytest_exit = int(pytest.main([*requested, "-q"], plugins=[Plugin()]))
    finally:
        sys.settrace(None)


def matches_request(nodeid):
    return any(nodeid == item or nodeid.startswith(item + "[") for item in requested)


missing = [
    item
    for item in requested
    if not any(nodeid == item or nodeid.startswith(item + "[") for nodeid in collected)
]
unrelated = [nodeid for nodeid in collected if not matches_request(nodeid)]
outcomes = {}
for nodeid in collected:
    row = records.get(nodeid, {})
    if row.get("wasxfail") and row.get("call") == "passed":
        outcome = "xpassed"
    elif row.get("wasxfail"):
        outcome = "xfailed"
    elif "failed" in row.values():
        outcome = "failed"
    elif "skipped" in row.values():
        outcome = "skipped"
    elif row.get("call") == "passed":
        outcome = "passed"
    else:
        outcome = "not_passed"
    outcomes[nodeid] = outcome

surface_results = []
for surface in subject.get("runtime_surfaces", []):
    path = os.path.normcase(os.path.abspath(surface["path"]))
    lines = executed_lines.get(path, set())
    observed = any(
        surface["line_start"] <= line <= surface["line_end"] for line in lines
    )
    surface_results.append({"surface_id": surface["surface_id"], "executed": observed})

oracle_results = []
for oracle in subject.get("oracle_checks", []):
    path = os.path.normcase(os.path.abspath(oracle["path"]))
    lines = executed_lines.get(path, set())
    observed = any(
        oracle["line_start"] <= line <= oracle["line_end"] for line in lines
    )
    oracle_results.append({
        "coverage_id": oracle["coverage_id"],
        "member_id": oracle["member_id"],
        "dimension": oracle["dimension"],
        "assertion_id": oracle["assertion_id"],
        "executed": observed,
    })

counts = {
    name: sum(value == name for value in outcomes.values())
    for name in ("passed", "failed", "skipped", "xfailed", "xpassed", "not_passed")
}
ok = bool(
    pytest_exit == 0
    and requested
    and collected
    and not missing
    and not unrelated
    and not deselected
    and counts["passed"] == len(collected)
    and all(item["executed"] for item in surface_results)
    and all(item["executed"] for item in oracle_results)
)
payload = {
    "schema_version": subject["result_schema_version"],
    "role": role,
    "subject_fingerprint": subject["subject_fingerprint"],
    "requested_nodeids": list(requested),
    "collected_nodeids": collected,
    "deselected_nodeids": deselected,
    "missing_nodeids": missing,
    "unrelated_nodeids": unrelated,
    "outcomes": outcomes,
    "counts": counts,
    "runtime_surface_results": surface_results,
    "oracle_results": oracle_results,
    "pytest_exit_code": pytest_exit,
    "pytest_stdout_fingerprint": __import__("hashlib").sha256(captured_stdout.getvalue().encode("utf-8")).hexdigest(),
    "pytest_stderr_fingerprint": __import__("hashlib").sha256(captured_stderr.getvalue().encode("utf-8")).hexdigest(),
    "ok": ok,
}
print("FLOWGUARD_SELF_REDUCTION_RESULT=" + json.dumps(payload, sort_keys=True, separators=(",", ":")))
raise SystemExit(0 if ok else 1)
'''


def _proof_obligation(kind: str, value: Any) -> str:
    """Content-address one exact proof subject without trusting an opaque id."""

    digest = fingerprint_value({"kind": str(kind), "value": value}).split(":", 1)[1]
    return f"self-reduction-proof:{kind}:{digest}"


def self_reduction_proof_obligation_ids(
    *,
    proof_id: str,
    subject_revision: str,
    inventory_fingerprint: str,
    test_inventory_fingerprint: str,
    candidate_id: str,
    candidate_signal: str,
    candidate_fingerprint: str,
    candidate_inventory_fingerprint: str,
    member_ids: tuple[str, ...],
    source_signal_ids: tuple[str, ...],
    caller_consumer_ids: tuple[str, ...],
    public_entrypoint_ids: tuple[str, ...],
    proof_status: str,
    observable_contract_fingerprint: str,
    test_evidence_ids: tuple[str, ...],
    coverage_ids: tuple[str, ...],
    parity_obligation_ids: tuple[str, ...] = SELF_REDUCTION_PARITY_OBLIGATION_IDS,
    public_facade_binding: dict[str, Any] | None = None,
) -> tuple[str, ...]:
    """Return the complete exact obligation set one leaf receipt must own."""

    normalized_members = tuple(sorted({str(value) for value in member_ids if str(value)}))
    normalized_tests = tuple(
        sorted({str(value) for value in test_evidence_ids if str(value)})
    )
    normalized_signals = tuple(
        sorted({str(value) for value in source_signal_ids if str(value)})
    )
    normalized_callers = tuple(
        sorted({str(value) for value in caller_consumer_ids if str(value)})
    )
    normalized_entrypoints = tuple(
        sorted({str(value) for value in public_entrypoint_ids if str(value)})
    )
    normalized_coverage = tuple(
        sorted({str(value) for value in coverage_ids if str(value)})
    )
    normalized_parity = tuple(
        sorted({str(value) for value in parity_obligation_ids if str(value)})
    )
    rows = {
        _proof_obligation("proof_id", str(proof_id)),
        _proof_obligation("subject_revision", str(subject_revision)),
        _proof_obligation("inventory_fingerprint", str(inventory_fingerprint)),
        _proof_obligation(
            "test_inventory_fingerprint",
            str(test_inventory_fingerprint),
        ),
        _proof_obligation("candidate_id", str(candidate_id)),
        _proof_obligation("candidate_signal", str(candidate_signal)),
        _proof_obligation("candidate_fingerprint", str(candidate_fingerprint)),
        _proof_obligation(
            "candidate_inventory_fingerprint",
            str(candidate_inventory_fingerprint),
        ),
        _proof_obligation("proof_status", str(proof_status)),
        _proof_obligation(
            "observable_contract_fingerprint",
            str(observable_contract_fingerprint),
        ),
        *(
            _proof_obligation("member_id", member_id)
            for member_id in normalized_members
        ),
        *(
            _proof_obligation("source_signal_id", signal_id)
            for signal_id in normalized_signals
        ),
        *(
            _proof_obligation("caller_consumer_id", caller_id)
            for caller_id in normalized_callers
        ),
        *(
            _proof_obligation("public_entrypoint_id", entrypoint_id)
            for entrypoint_id in normalized_entrypoints
        ),
        *(
            _proof_obligation("test_evidence_id", test_id)
            for test_id in normalized_tests
        ),
        *(
            _proof_obligation("coverage_id", coverage_id)
            for coverage_id in normalized_coverage
        ),
        *(
            _proof_obligation("parity_obligation_id", obligation_id)
            for obligation_id in normalized_parity
        ),
    }
    if public_facade_binding is not None:
        rows.add(_proof_obligation("public_facade_binding", public_facade_binding))
    return tuple(sorted(rows))


_SELF_REDUCTION_PROOF_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "proof_id",
        "subject_revision",
        "inventory_fingerprint",
        "test_inventory_fingerprint",
        "candidate_id",
        "candidate_signal",
        "candidate_fingerprint",
        "candidate_inventory_fingerprint",
        "member_ids",
        "source_signal_ids",
        "caller_consumer_ids",
        "public_entrypoint_ids",
        "proof_status",
        "observable_contract_fingerprint",
        "test_evidence_ids",
        "coverage_ids",
        "parity_results",
        "public_facade_binding",
    }
)
_SELF_REDUCTION_PUBLIC_FACADE_FIELDS = frozenset(
    {
        "public_facade_delegation_evidence_id",
        "business_intent_id",
        "behavior_commitment_id",
        "primary_path_id",
        "owner_code_contract_id",
        "delegates_to_code_contract_id",
        "delegates_to_primary_path_id",
        "delegation_only",
        "independent_business_authority",
    }
)


def _deterministic_self_reduction_proof_id(
    proof_payload: Mapping[str, Any],
) -> str:
    """Derive one proof id from its entire semantic subject, not caller text."""

    identity = {
        str(key): value
        for key, value in proof_payload.items()
        if str(key) != "proof_id"
    }
    digest = fingerprint_value(identity).split(":", 1)[1]
    return f"proof:self-reduction:{digest}"


def _strict_canonical_string_list(
    value: Any,
    *,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(
            f"self reduction proof {field_name} must be an array of strings"
        )
    normalized = tuple(sorted(set(value)))
    if list(normalized) != value:
        raise ValueError(
            f"self reduction proof {field_name} must be sorted and unique"
        )
    return normalized


@dataclass(frozen=True)
class SelfReductionProofSelection:
    """One candidate selected from an already frozen batch inventory."""

    candidate_id: str
    candidate_fingerprint: str
    proof_status: str = PROOF_SAFE_BY_EQUIVALENCE

    def __post_init__(self) -> None:
        for name in ("candidate_id", "candidate_fingerprint"):
            value = str(getattr(self, name, "")).strip()
            if not value:
                raise ValueError(f"self reduction proof selection requires {name}")
            object.__setattr__(self, name, value)
        if self.proof_status not in {
            PROOF_SAFE_BY_EQUIVALENCE,
            PROOF_SAFE_BY_PUBLIC_FACADE,
        }:
            raise ValueError(
                "self reduction proof selection status is not contraction-ready"
            )


@dataclass(frozen=True)
class SelfReductionProofRecord:
    """Minimal reference to one canonical child-bound candidate proof."""

    proof_id: str
    subject_revision: str
    inventory_fingerprint: str
    test_inventory_fingerprint: str
    candidate_id: str
    candidate_signal: str
    candidate_fingerprint: str
    candidate_inventory_fingerprint: str
    member_ids: tuple[str, ...]
    source_signal_ids: tuple[str, ...]
    caller_consumer_ids: tuple[str, ...]
    public_entrypoint_ids: tuple[str, ...]
    proof_status: str
    observable_contract_fingerprint: str
    test_evidence_ids: tuple[str, ...]
    coverage_ids: tuple[str, ...]
    aggregate_receipt_id: str
    public_facade_delegation_evidence_id: str = ""
    business_intent_id: str = ""
    behavior_commitment_id: str = ""
    primary_path_id: str = ""
    owner_code_contract_id: str = ""
    delegates_to_code_contract_id: str = ""
    delegates_to_primary_path_id: str = ""
    delegation_only: bool = False
    independent_business_authority: bool = False

    def __post_init__(self) -> None:
        for name in (
            "proof_id",
            "subject_revision",
            "inventory_fingerprint",
            "test_inventory_fingerprint",
            "candidate_id",
            "candidate_signal",
            "candidate_fingerprint",
            "candidate_inventory_fingerprint",
            "observable_contract_fingerprint",
            "aggregate_receipt_id",
        ):
            if not str(getattr(self, name, "")).strip():
                raise ValueError(f"self reduction proof requires {name}")
        object.__setattr__(self, "candidate_signal", str(self.candidate_signal))
        object.__setattr__(
            self,
            "member_ids",
            tuple(sorted({str(value) for value in self.member_ids if str(value)})),
        )
        object.__setattr__(
            self,
            "source_signal_ids",
            tuple(
                sorted({str(value) for value in self.source_signal_ids if str(value)})
            ),
        )
        for name in ("caller_consumer_ids", "public_entrypoint_ids"):
            object.__setattr__(
                self,
                name,
                tuple(
                    sorted(
                        {
                            str(value)
                            for value in getattr(self, name)
                            if str(value)
                        }
                    )
                ),
            )
        object.__setattr__(
            self,
            "test_evidence_ids",
            tuple(
                sorted({str(value) for value in self.test_evidence_ids if str(value)})
            ),
        )
        object.__setattr__(
            self,
            "coverage_ids",
            tuple(sorted({str(value) for value in self.coverage_ids if str(value)})),
        )
        if not self.member_ids or not self.test_evidence_ids:
            raise ValueError(
                "self reduction proof requires exact members and tests"
            )
        if not self.source_signal_ids or not self.coverage_ids:
            raise ValueError(
                "self reduction proof requires exact source signals and coverage"
            )
        if self.proof_status not in {
            PROOF_SAFE_BY_EQUIVALENCE,
            PROOF_SAFE_BY_PUBLIC_FACADE,
        }:
            raise ValueError("self reduction proof status is not contraction-ready")
        if (
            self.proof_status == PROOF_SAFE_BY_PUBLIC_FACADE
            and (
                not self.public_facade_delegation_evidence_id
                or not self.business_intent_id
                or not self.behavior_commitment_id
                or not self.primary_path_id
                or not self.owner_code_contract_id
                or self.delegates_to_code_contract_id
                != self.owner_code_contract_id
                or self.delegates_to_primary_path_id != self.primary_path_id
                or not self.delegation_only
                or self.independent_business_authority
            )
        ):
            raise ValueError(
                "public-facade proof requires exact single-authority delegation evidence"
            )
        if self.proof_status == PROOF_SAFE_BY_EQUIVALENCE and any(
            (
                self.public_facade_delegation_evidence_id,
                self.business_intent_id,
                self.behavior_commitment_id,
                self.primary_path_id,
                self.owner_code_contract_id,
                self.delegates_to_code_contract_id,
                self.delegates_to_primary_path_id,
                self.delegation_only,
                self.independent_business_authority,
            )
        ):
            raise ValueError(
                "equivalence proof cannot carry a hidden public-facade authority path"
            )
        if not self.aggregate_receipt_id.startswith(
            "receipt:validation-owner:self-reduction-aggregate-"
        ):
            raise ValueError(
                "self reduction proof requires a canonical aggregate receipt id"
            )
        expected_proof_id = _deterministic_self_reduction_proof_id(
            self.canonical_evidence_payload
        )
        if self.proof_id != expected_proof_id:
            raise ValueError(
                "self reduction proof id does not match its canonical semantic subject"
            )

    @classmethod
    def from_canonical_evidence_payload(
        cls,
        payload: Any,
        *,
        aggregate_receipt_id: str,
    ) -> "SelfReductionProofRecord":
        """Strictly rebuild one record from its canonical aggregate artifact."""

        if not isinstance(payload, Mapping):
            raise ValueError("self reduction proof payload must be an object")
        data = dict(payload)
        if set(data) != _SELF_REDUCTION_PROOF_PAYLOAD_FIELDS:
            raise ValueError(
                "self reduction proof payload does not use the current exact schema"
            )
        if data.get("schema_version") != SELF_REDUCTION_PROOF_RECORD_SCHEMA:
            raise ValueError("self reduction proof payload schema is stale")
        string_fields = (
            "proof_id",
            "subject_revision",
            "inventory_fingerprint",
            "test_inventory_fingerprint",
            "candidate_id",
            "candidate_signal",
            "candidate_fingerprint",
            "candidate_inventory_fingerprint",
            "proof_status",
            "observable_contract_fingerprint",
        )
        if any(
            not isinstance(data.get(name), str) or not data[name]
            for name in string_fields
        ):
            raise ValueError(
                "self reduction proof payload requires exact non-empty string identities"
            )
        parity_results = data.get("parity_results")
        if parity_results != {
            obligation_id: RECEIPT_STATUS_PASS
            for obligation_id in SELF_REDUCTION_PARITY_OBLIGATION_IDS
        }:
            raise ValueError(
                "self reduction proof payload requires the exact parity result set"
            )
        facade = data.get("public_facade_binding")
        if facade is not None:
            if not isinstance(facade, Mapping) or set(facade) != (
                _SELF_REDUCTION_PUBLIC_FACADE_FIELDS
            ):
                raise ValueError(
                    "self reduction proof public-facade binding has a non-current shape"
                )
            facade = dict(facade)
            string_facade_fields = _SELF_REDUCTION_PUBLIC_FACADE_FIELDS - {
                "delegation_only",
                "independent_business_authority",
            }
            if any(
                not isinstance(facade.get(name), str)
                for name in string_facade_fields
            ) or any(
                not isinstance(facade.get(name), bool)
                for name in ("delegation_only", "independent_business_authority")
            ):
                raise ValueError(
                    "self reduction proof public-facade binding has invalid field types"
                )
        record = cls(
            proof_id=data["proof_id"],
            subject_revision=data["subject_revision"],
            inventory_fingerprint=data["inventory_fingerprint"],
            test_inventory_fingerprint=data["test_inventory_fingerprint"],
            candidate_id=data["candidate_id"],
            candidate_signal=data["candidate_signal"],
            candidate_fingerprint=data["candidate_fingerprint"],
            candidate_inventory_fingerprint=data[
                "candidate_inventory_fingerprint"
            ],
            member_ids=_strict_canonical_string_list(
                data["member_ids"], field_name="member_ids"
            ),
            source_signal_ids=_strict_canonical_string_list(
                data["source_signal_ids"], field_name="source_signal_ids"
            ),
            caller_consumer_ids=_strict_canonical_string_list(
                data["caller_consumer_ids"], field_name="caller_consumer_ids"
            ),
            public_entrypoint_ids=_strict_canonical_string_list(
                data["public_entrypoint_ids"], field_name="public_entrypoint_ids"
            ),
            proof_status=data["proof_status"],
            observable_contract_fingerprint=data[
                "observable_contract_fingerprint"
            ],
            test_evidence_ids=_strict_canonical_string_list(
                data["test_evidence_ids"], field_name="test_evidence_ids"
            ),
            coverage_ids=_strict_canonical_string_list(
                data["coverage_ids"], field_name="coverage_ids"
            ),
            aggregate_receipt_id=str(aggregate_receipt_id),
            public_facade_delegation_evidence_id=str(
                (facade or {}).get("public_facade_delegation_evidence_id", "")
            ),
            business_intent_id=str((facade or {}).get("business_intent_id", "")),
            behavior_commitment_id=str(
                (facade or {}).get("behavior_commitment_id", "")
            ),
            primary_path_id=str((facade or {}).get("primary_path_id", "")),
            owner_code_contract_id=str(
                (facade or {}).get("owner_code_contract_id", "")
            ),
            delegates_to_code_contract_id=str(
                (facade or {}).get("delegates_to_code_contract_id", "")
            ),
            delegates_to_primary_path_id=str(
                (facade or {}).get("delegates_to_primary_path_id", "")
            ),
            delegation_only=bool((facade or {}).get("delegation_only", False)),
            independent_business_authority=bool(
                (facade or {}).get("independent_business_authority", False)
            ),
        )
        if record.canonical_evidence_payload != data:
            raise ValueError(
                "self reduction proof payload is not in canonical current form"
            )
        return record

    @property
    def public_facade_binding(self) -> dict[str, Any] | None:
        if self.proof_status != PROOF_SAFE_BY_PUBLIC_FACADE:
            return None
        return {
            "public_facade_delegation_evidence_id": (
                self.public_facade_delegation_evidence_id
            ),
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "primary_path_id": self.primary_path_id,
            "owner_code_contract_id": self.owner_code_contract_id,
            "delegates_to_code_contract_id": self.delegates_to_code_contract_id,
            "delegates_to_primary_path_id": self.delegates_to_primary_path_id,
            "delegation_only": self.delegation_only,
            "independent_business_authority": (
                self.independent_business_authority
            ),
        }

    @property
    def canonical_evidence_payload(self) -> dict[str, Any]:
        """Exact semantic payload that the canonical owner proof must contain."""

        return {
            "schema_version": SELF_REDUCTION_PROOF_RECORD_SCHEMA,
            "proof_id": self.proof_id,
            "subject_revision": self.subject_revision,
            "inventory_fingerprint": self.inventory_fingerprint,
            "test_inventory_fingerprint": self.test_inventory_fingerprint,
            "candidate_id": self.candidate_id,
            "candidate_signal": self.candidate_signal,
            "candidate_fingerprint": self.candidate_fingerprint,
            "candidate_inventory_fingerprint": (
                self.candidate_inventory_fingerprint
            ),
            "member_ids": list(self.member_ids),
            "source_signal_ids": list(self.source_signal_ids),
            "caller_consumer_ids": list(self.caller_consumer_ids),
            "public_entrypoint_ids": list(self.public_entrypoint_ids),
            "proof_status": self.proof_status,
            "observable_contract_fingerprint": (
                self.observable_contract_fingerprint
            ),
            "test_evidence_ids": list(self.test_evidence_ids),
            "coverage_ids": list(self.coverage_ids),
            "parity_results": {
                obligation_id: RECEIPT_STATUS_PASS
                for obligation_id in SELF_REDUCTION_PARITY_OBLIGATION_IDS
            },
            "public_facade_binding": self.public_facade_binding,
        }

    @property
    def required_obligation_ids(self) -> tuple[str, ...]:
        return self_reduction_proof_obligation_ids(
            proof_id=self.proof_id,
            subject_revision=self.subject_revision,
            inventory_fingerprint=self.inventory_fingerprint,
            test_inventory_fingerprint=self.test_inventory_fingerprint,
            candidate_id=self.candidate_id,
            candidate_signal=self.candidate_signal,
            candidate_fingerprint=self.candidate_fingerprint,
            candidate_inventory_fingerprint=(
                self.candidate_inventory_fingerprint
            ),
            member_ids=self.member_ids,
            source_signal_ids=self.source_signal_ids,
            caller_consumer_ids=self.caller_consumer_ids,
            public_entrypoint_ids=self.public_entrypoint_ids,
            proof_status=self.proof_status,
            observable_contract_fingerprint=self.observable_contract_fingerprint,
            test_evidence_ids=self.test_evidence_ids,
            coverage_ids=self.coverage_ids,
            parity_obligation_ids=SELF_REDUCTION_PARITY_OBLIGATION_IDS,
            public_facade_binding=self.public_facade_binding,
        )

    @property
    def proof_owner_id(self) -> str:
        return _proof_owner_ids(self.canonical_evidence_payload)[2]

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        """Only typed immutable receipt artifacts become candidate evidence refs."""

        return (self.aggregate_receipt_id,)

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    @property
    def complete(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "proof_owner_id": self.proof_owner_id,
            "subject_revision": self.subject_revision,
            "inventory_fingerprint": self.inventory_fingerprint,
            "test_inventory_fingerprint": self.test_inventory_fingerprint,
            "candidate_id": self.candidate_id,
            "candidate_signal": self.candidate_signal,
            "candidate_fingerprint": self.candidate_fingerprint,
            "candidate_inventory_fingerprint": (
                self.candidate_inventory_fingerprint
            ),
            "member_ids": list(self.member_ids),
            "source_signal_ids": list(self.source_signal_ids),
            "caller_consumer_ids": list(self.caller_consumer_ids),
            "public_entrypoint_ids": list(self.public_entrypoint_ids),
            "proof_status": self.proof_status,
            "observable_contract_fingerprint": self.observable_contract_fingerprint,
            "test_evidence_ids": list(self.test_evidence_ids),
            "coverage_ids": list(self.coverage_ids),
            "parity_obligation_ids": list(SELF_REDUCTION_PARITY_OBLIGATION_IDS),
            "required_obligation_ids": list(self.required_obligation_ids),
            "aggregate_receipt_id": self.aggregate_receipt_id,
            "public_facade_delegation_evidence_id": (
                self.public_facade_delegation_evidence_id
            ),
            "business_intent_id": self.business_intent_id,
            "behavior_commitment_id": self.behavior_commitment_id,
            "primary_path_id": self.primary_path_id,
            "owner_code_contract_id": self.owner_code_contract_id,
            "delegates_to_code_contract_id": self.delegates_to_code_contract_id,
            "delegates_to_primary_path_id": self.delegates_to_primary_path_id,
            "delegation_only": self.delegation_only,
            "independent_business_authority": self.independent_business_authority,
        }


_VERIFIED_SELF_REDUCTION_PROOF_FORWARD_FIELDS = frozenset(
    {
        "aggregate_receipt_id",
        "behavior_commitment_id",
        "business_intent_id",
        "candidate_id",
        "candidate_signal",
        "candidate_fingerprint",
        "candidate_inventory_fingerprint",
        "caller_consumer_ids",
        "coverage_ids",
        "delegates_to_code_contract_id",
        "delegates_to_primary_path_id",
        "delegation_only",
        "independent_business_authority",
        "inventory_fingerprint",
        "member_ids",
        "observable_contract_fingerprint",
        "owner_code_contract_id",
        "primary_path_id",
        "proof_id",
        "proof_status",
        "public_entrypoint_ids",
        "public_facade_delegation_evidence_id",
        "source_signal_ids",
        "subject_revision",
        "test_evidence_ids",
        "test_inventory_fingerprint",
    }
)


@dataclass(frozen=True)
class _VerifiedSelfReductionProof:
    record: SelfReductionProofRecord
    aggregate_receipt: EvidenceReceipt
    aggregate_verification: ReceiptVerificationResult
    child_receipts: tuple[EvidenceReceipt, ...]
    child_verifications: tuple[ReceiptVerificationResult, ...]
    owner_contracts: tuple[ValidationOwnerContract, ...]
    owner_identities: tuple[str, ...]
    episode_tokens: tuple[str, ...]

    def __getattr__(self, name: str) -> Any:
        if name not in _VERIFIED_SELF_REDUCTION_PROOF_FORWARD_FIELDS:
            raise AttributeError(
                f"verified self-reduction proof does not expose {name!r}"
            )
        return getattr(self.record, name)

    @property
    def complete(self) -> bool:
        return True

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict())

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        return (
            self.aggregate_receipt.receipt_id,
            self.aggregate_receipt.fingerprint,
            self.aggregate_receipt.proof_artifact_id,
            self.aggregate_receipt.proof_artifact_fingerprint,
            *(item.receipt_id for item in self.child_receipts),
            *(item.fingerprint for item in self.child_receipts),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "aggregate_receipt_id": self.aggregate_receipt.receipt_id,
            "aggregate_receipt_fingerprint": self.aggregate_receipt.fingerprint,
            "child_receipt_ids": [item.receipt_id for item in self.child_receipts],
            "child_receipt_fingerprints": [
                item.fingerprint for item in self.child_receipts
            ],
            "owner_identities": list(self.owner_identities),
            "episode_tokens": list(self.episode_tokens),
        }


def self_reduction_proof_projected_inputs(
    *,
    subject_revision: str,
    inventory_fingerprint: str,
    test_inventory_fingerprint: str,
    proof_payload: dict[str, Any],
) -> tuple[tuple[str, str], ...]:
    """Return the exact current subject projections one proof owner must consume."""

    return tuple(
        sorted(
            (
                (
                    "self-reduction:subject-revision",
                    fingerprint_value(
                        {"subject_revision": str(subject_revision)}
                    ),
                ),
                (
                    "self-reduction:implementation-inventory",
                    str(inventory_fingerprint),
                ),
                (
                    "self-reduction:test-inventory",
                    str(test_inventory_fingerprint),
                ),
                (
                    "self-reduction:proof-subject",
                    fingerprint_value(proof_payload),
                ),
            )
        )
    )


def _path_is_reparse(path: Path) -> bool:
    """Recognize every Python-visible link/junction/reparse path boundary."""

    try:
        if path.is_symlink():
            return True
        is_junction = getattr(os.path, "isjunction", None)
        if is_junction is not None and is_junction(path):
            return True
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(
        attributes
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _assert_non_reparse_components(
    root: Path,
    target: Path,
    *,
    include_target: bool = True,
) -> None:
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "self reduction proof path escapes the repository"
        ) from exc
    current = root
    rows = relative.parts if include_target else relative.parts[:-1]
    for part in rows:
        current = current / part
        if current.exists() and _path_is_reparse(current):
            raise ValueError(
                "self reduction proof path traverses a symlink, junction, or reparse point"
            )


def _resolved_repository_root(root: str | Path) -> Path:
    lexical = Path(os.path.abspath(os.fspath(root)))
    if not lexical.is_dir():
        raise ValueError("self reduction repository root is missing")
    if _path_is_reparse(lexical):
        raise ValueError(
            "self reduction repository root cannot be a symlink, junction, or reparse point"
        )
    return lexical.resolve(strict=True)


def _canonical_validation_owner_root(root: str | Path) -> Path:
    root_path = _resolved_repository_root(root)
    canonical = root_path / _CANONICAL_VALIDATION_OWNER_RELATIVE
    _assert_non_reparse_components(root_path, canonical)
    if canonical.exists() and canonical.resolve(strict=True) != canonical:
        raise ValueError(
            "self reduction canonical proof store resolves outside its direct path"
        )
    return canonical


def _confined_regular_file(
    root: Path,
    relative: str | Path,
    *,
    missing_message: str,
) -> Path:
    relative_path = Path(relative)
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise ValueError("self reduction proof path escapes its canonical store")
    candidate = root / relative_path
    _assert_non_reparse_components(root, candidate)
    if not candidate.is_file() or candidate.resolve(strict=True) != candidate:
        raise ValueError(missing_message)
    return candidate


def _proof_owner_ids(proof_payload: dict[str, Any]) -> tuple[str, str, str]:
    digest = fingerprint_value(proof_payload).split(":", 1)[1][:32]
    return (
        f"self-reduction-test-{digest}",
        f"self-reduction-parity-{digest}",
        f"self-reduction-aggregate-{digest}",
    )


def _normalized_candidate_observable_contract(
    candidate: ArchitectureReductionCandidate,
) -> dict[str, Any]:
    metadata = dict(candidate.metadata)
    raw_contract = metadata.get("observable_contract")
    if not isinstance(raw_contract, dict):
        raise ValueError(
            "self reduction candidate requires one normalized observable contract"
        )
    contract = dict(raw_contract)
    expected_fields = {
        "schema_version",
        "caller_consumer_ids",
        "behavior_block_ids",
        "model_element_ids",
        "owner_ids",
        "state_reads",
        "state_writes",
        "side_effect_ids",
        "raised_error_ids",
        "evidence_neighborhood_id",
        "evidence_neighborhood_fingerprint",
    }
    if set(contract) != expected_fields:
        inline_fields = sorted(
            set(contract) & _INLINE_EVIDENCE_NEIGHBORHOOD_FIELDS
        )
        if inline_fields:
            raise ValueError(
                "self reduction candidate cannot carry an inline evidence "
                "neighborhood fallback: " + ", ".join(inline_fields)
            )
        raise ValueError(
            "self reduction candidate observable contract has an incomplete "
            "direct-current schema"
        )
    if (
        contract["schema_version"]
        != SELF_REDUCTION_OBSERVABLE_CONTRACT_SCHEMA
    ):
        raise ValueError(
            "self reduction candidate observable contract schema is stale"
        )
    for name in (
        "caller_consumer_ids",
        "behavior_block_ids",
        "model_element_ids",
        "owner_ids",
        "state_reads",
        "state_writes",
        "side_effect_ids",
        "raised_error_ids",
    ):
        values = tuple(str(value) for value in contract[name] if str(value))
        if values != tuple(sorted(set(values))):
            raise ValueError(
                "self reduction candidate observable contract arrays must be "
                f"canonical: {name}"
            )
        contract[name] = values
    for name in (
        "evidence_neighborhood_id",
        "evidence_neighborhood_fingerprint",
    ):
        contract[name] = str(contract[name])
        if not contract[name]:
            raise ValueError(
                "self reduction candidate observable contract requires " + name
            )
    expected_fingerprint = fingerprint_value(contract)
    if (
        str(metadata.get("observable_contract_fingerprint", ""))
        != expected_fingerprint
    ):
        raise ValueError(
            "self reduction candidate observable contract fingerprint mismatch"
        )
    return contract


def _resolved_candidate_observable_contract(
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
) -> dict[str, Any]:
    """Resolve and independently re-observe one candidate's exact evidence."""

    contract = _normalized_candidate_observable_contract(candidate)
    member_ids = {
        str(value)
        for value in candidate.metadata.get("member_ids", ())
        if str(value)
    }
    behavior_ids = set(contract["behavior_block_ids"])
    coverage_execution: dict[str, Any] = {}
    for row in getattr(
        bundle.behavior_report,
        "coverage_execution_evidence",
        (),
    ):
        coverage_id = str(getattr(row, "coverage_id", ""))
        if coverage_id:
            coverage_execution[coverage_id] = row
    test_ids: set[str] = set()
    coverage_ids: set[str] = set()
    covered_dimensions: set[str] = set()
    current_test_receipt_ids: set[str] = set()
    for row in getattr(bundle.behavior_report, "coverage_edges", ()):
        surface_id = str(
            getattr(row, "implementation_surface_id", "")
        )
        behavior_id = str(getattr(row, "behavior_block_id", ""))
        if surface_id not in member_ids and behavior_id not in behavior_ids:
            continue
        coverage_id = str(getattr(row, "coverage_id", ""))
        test_id = str(getattr(row, "test_node_id", ""))
        if coverage_id:
            coverage_ids.add(coverage_id)
        if test_id:
            test_ids.add(test_id)
        covered_dimensions.update(
            str(value)
            for value in getattr(row, "covered_dimensions", ())
            if str(value)
        )
        execution = coverage_execution.get(coverage_id)
        if (
            execution is not None
            and str(getattr(execution, "disposition", "")) == "pass"
        ):
            receipt_id = str(getattr(execution, "receipt_id", ""))
            if receipt_id:
                current_test_receipt_ids.add(receipt_id)
    neighborhood = SelfReductionEvidenceNeighborhood(
        test_node_ids=tuple(test_ids),
        coverage_ids=tuple(coverage_ids),
        covered_dimensions=tuple(covered_dimensions),
        current_test_receipt_ids=tuple(current_test_receipt_ids),
    )
    if (
        neighborhood.neighborhood_id
        != contract["evidence_neighborhood_id"]
        or neighborhood.fingerprint
        != contract["evidence_neighborhood_fingerprint"]
    ):
        raise ValueError(
            "self reduction candidate evidence neighborhood is stale for the "
            "current behavior report"
        )
    return {
        "caller_consumer_ids": contract["caller_consumer_ids"],
        "behavior_block_ids": contract["behavior_block_ids"],
        "model_element_ids": contract["model_element_ids"],
        "owner_ids": contract["owner_ids"],
        "state_reads": contract["state_reads"],
        "state_writes": contract["state_writes"],
        "side_effect_ids": contract["side_effect_ids"],
        "raised_error_ids": contract["raised_error_ids"],
        "test_node_ids": neighborhood.test_node_ids,
        "coverage_ids": neighborhood.coverage_ids,
        "covered_dimensions": neighborhood.covered_dimensions,
        "current_test_receipt_ids": (
            neighborhood.current_test_receipt_ids
        ),
    }


def _candidate_binding(
    candidate: ArchitectureReductionCandidate,
) -> SelfReductionCandidateBinding:
    metadata = dict(candidate.metadata)
    _normalized_candidate_observable_contract(candidate)
    return SelfReductionCandidateBinding(
        candidate_id=candidate.candidate_id,
        signal=str(metadata.get("signal", "")),
        member_ids=tuple(metadata.get("member_ids", ())),
        source_signal_ids=tuple(metadata.get("source_signal_ids", ())),
        observable_contract_fingerprint=str(
            metadata["observable_contract_fingerprint"]
        ),
        caller_ids=tuple(metadata.get("caller_ids", ())),
        public_entrypoint_ids=tuple(
            metadata.get("public_entrypoint_ids", ())
        ),
        caller_resolution_gap_ids=tuple(
            metadata.get("caller_resolution_gap_ids", ())
        ),
    )


def _assertion_target_is_semantic(target: str) -> bool:
    """Reject assertions whose truth is fixed without observing runtime behavior."""

    normalized = str(target).strip()
    if not normalized:
        return False
    try:
        expression = ast.parse(normalized, mode="eval")
    except SyntaxError:
        return False
    try:
        ast.literal_eval(expression.body)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        pass
    else:
        return False
    runtime_nodes = (
        ast.Name,
        ast.Attribute,
        ast.Subscript,
        ast.Call,
        ast.Await,
    )
    return any(isinstance(node, runtime_nodes) for node in ast.walk(expression))


def _candidate_semantic_bindings(
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
    *,
    test_ids: tuple[str, ...],
    coverage_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    """Bind every affected member and dimension to one real test assertion/case."""

    behavior_report = bundle.behavior_report
    contracts = tuple(getattr(behavior_report, "contracts", ()))
    supporting = tuple(getattr(behavior_report, "supporting_relations", ()))
    cases = {
        str(getattr(row, "case_id", "")): row
        for row in getattr(behavior_report, "case_contracts", ())
        if str(getattr(row, "case_id", ""))
    }
    coverage_by_id = {
        str(getattr(row, "coverage_id", "")): row
        for row in getattr(behavior_report, "coverage_edges", ())
        if str(getattr(row, "coverage_id", ""))
    }
    test_by_id = {
        str(getattr(row, "node_id", "")): row
        for row in getattr(bundle.test_inventory, "nodes", ())
        if str(getattr(row, "node_id", ""))
    }
    assertion_owner: dict[str, tuple[str, Any]] = {}
    for test_id in test_ids:
        test = test_by_id[test_id]
        assertions = tuple(getattr(test, "assertions", ()))
        if not assertions:
            raise ValueError(
                "self reduction candidate test has no exact runtime assertion members"
            )
        for assertion in assertions:
            assertion_id = str(getattr(assertion, "assertion_id", ""))
            if not assertion_id or assertion_id in assertion_owner:
                raise ValueError(
                    "self reduction candidate test assertion identity is missing or ambiguous"
                )
            assertion_owner[assertion_id] = (test_id, assertion)

    direct_by_surface: dict[str, set[str]] = {}
    owner_surface_by_behavior: dict[str, set[str]] = {}
    for contract in contracts:
        surface_id = str(getattr(contract, "implementation_surface_id", ""))
        behavior_id = str(getattr(contract, "behavior_block_id", ""))
        if surface_id and behavior_id:
            direct_by_surface.setdefault(surface_id, set()).add(behavior_id)
            owner_surface_by_behavior.setdefault(behavior_id, set()).add(surface_id)
    supporting_by_surface: dict[str, set[str]] = {}
    for relation in supporting:
        surface_id = str(getattr(relation, "supporting_surface_id", ""))
        behavior_id = str(getattr(relation, "behavior_block_id", ""))
        if surface_id and behavior_id:
            supporting_by_surface.setdefault(surface_id, set()).add(behavior_id)

    candidate_members = tuple(
        sorted(
            {
                str(value)
                for value in (
                    *candidate.metadata.get("member_ids", ()),
                    *candidate.affected_public_entrypoints,
                )
                if str(value)
            }
        )
    )
    required_dimensions = {"input", "output", "state", "effect", "error"}
    bindings: list[dict[str, Any]] = []
    used_coverage_ids: set[str] = set()
    used_test_ids: set[str] = set()
    for member_id in candidate_members:
        behavior_ids = tuple(
            sorted(
                direct_by_surface.get(member_id, set())
                | supporting_by_surface.get(member_id, set())
            )
        )
        if not behavior_ids:
            raise ValueError(
                f"self reduction member has no current behavior/model binding: {member_id}"
            )
        member_dimensions: set[str] = set()
        member_binding_count = 0
        for behavior_id in behavior_ids:
            matching = tuple(
                coverage_by_id[coverage_id]
                for coverage_id in coverage_ids
                if str(
                    getattr(coverage_by_id[coverage_id], "behavior_block_id", "")
                )
                == behavior_id
            )
            if not matching:
                raise ValueError(
                    "self reduction member behavior has no exact current case/oracle coverage: "
                    + member_id
                )
            for coverage in matching:
                coverage_id = str(coverage.coverage_id)
                dimensions = tuple(
                    str(value)
                    for value in getattr(coverage, "covered_dimensions", ())
                    if str(value)
                )
                if len(dimensions) != 1 or dimensions[0] not in required_dimensions:
                    raise ValueError(
                        "self reduction coverage must bind one exact behavior dimension"
                    )
                dimension = dimensions[0]
                test_id = str(getattr(coverage, "test_node_id", ""))
                assertion_id = str(getattr(coverage, "oracle_member_id", ""))
                assertion_entry = assertion_owner.get(assertion_id)
                if (
                    test_id not in test_ids
                    or assertion_entry is None
                    or assertion_entry[0] != test_id
                ):
                    raise ValueError(
                        "self reduction coverage is not owned by its exact test assertion"
                    )
                assertion = assertion_entry[1]
                if (
                    str(getattr(assertion, "structure_fingerprint", ""))
                    != str(getattr(coverage, "oracle_member_fingerprint", ""))
                ):
                    raise ValueError(
                        "self reduction coverage assertion fingerprint is stale"
                    )
                if not _assertion_target_is_semantic(
                    str(getattr(assertion, "target", ""))
                ):
                    raise ValueError(
                        "self reduction proof cannot use a trivial or non-semantic assertion"
                    )
                case_id = str(getattr(coverage, "case_id", ""))
                case = cases.get(case_id)
                if case is None:
                    raise ValueError(
                        "self reduction coverage has no exact current behavior case"
                    )
                if (
                    str(getattr(case, "behavior_block_id", "")) != behavior_id
                    or str(getattr(case, "content_fingerprint", ""))
                    != str(getattr(coverage, "case_content_fingerprint", ""))
                    or str(getattr(case, "oracle_id", ""))
                    != str(getattr(coverage, "oracle_id", ""))
                ):
                    raise ValueError(
                        "self reduction coverage case/oracle binding is stale"
                    )
                owner_surface_ids = tuple(
                    sorted(owner_surface_by_behavior.get(behavior_id, ()))
                )
                if len(owner_surface_ids) != 1:
                    raise ValueError(
                        "self reduction behavior must have one exact implementation owner"
                    )
                bindings.append(
                    {
                        "member_id": member_id,
                        "behavior_block_id": behavior_id,
                        "behavior_owner_surface_id": owner_surface_ids[0],
                        "coverage_id": coverage_id,
                        "dimension": dimension,
                        "test_node_id": test_id,
                        "assertion_id": assertion_id,
                        "assertion_fingerprint": str(
                            getattr(assertion, "structure_fingerprint", "")
                        ),
                        "assertion_target": str(getattr(assertion, "target", "")),
                        "assertion_line_start": int(
                            getattr(assertion, "line_start", 0)
                        ),
                        "assertion_line_end": int(
                            getattr(assertion, "line_end", 0)
                        ),
                        "case_id": case_id,
                        "case_content_fingerprint": str(
                            getattr(case, "content_fingerprint", "")
                        ),
                        "case_kind": str(getattr(case, "case_kind", "")),
                        "input_values": dict(getattr(case, "input_values", ())),
                        "initial_state": dict(getattr(case, "initial_state", ())),
                        "expected_output": dict(
                            getattr(case, "expected_output", ())
                        ),
                        "expected_state": dict(
                            getattr(case, "expected_state", ())
                        ),
                        "expected_effects": list(
                            getattr(case, "expected_effects", ())
                        ),
                        "expected_errors": list(
                            getattr(case, "expected_errors", ())
                        ),
                        "oracle_id": str(getattr(case, "oracle_id", "")),
                    }
                )
                member_dimensions.add(dimension)
                member_binding_count += 1
                used_coverage_ids.add(coverage_id)
                used_test_ids.add(test_id)
        if member_binding_count == 0 or member_dimensions != required_dimensions:
            raise ValueError(
                "self reduction candidate does not bind every member to input/output/state/effect/error oracles"
            )
    if used_coverage_ids != set(coverage_ids) or used_test_ids != set(test_ids):
        raise ValueError(
            "self reduction candidate includes unrelated test or coverage evidence"
        )
    return tuple(
        sorted(
            bindings,
            key=lambda row: (
                row["member_id"],
                row["behavior_block_id"],
                row["dimension"],
                row["coverage_id"],
            ),
        )
    )


def _proof_test_details(
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    observable = _resolved_candidate_observable_contract(bundle, candidate)
    caller_gap_ids = tuple(
        str(value)
        for value in candidate.metadata.get("caller_resolution_gap_ids", ())
        if str(value)
    )
    if caller_gap_ids:
        raise ValueError(
            "self reduction candidate has ambiguous caller relations: "
            + ", ".join(sorted(caller_gap_ids))
        )
    test_ids = tuple(
        sorted({str(value) for value in observable.get("test_node_ids", ()) if str(value)})
    )
    coverage_ids = tuple(
        sorted({str(value) for value in observable.get("coverage_ids", ()) if str(value)})
    )
    if not test_ids or not coverage_ids:
        raise ValueError(
            "self reduction candidate has no exact observable-contract test coverage"
        )
    coverage_by_id = {
        str(getattr(row, "coverage_id", "")): row
        for row in getattr(bundle.behavior_report, "coverage_edges", ())
        if str(getattr(row, "coverage_id", ""))
    }
    if set(coverage_ids) - set(coverage_by_id):
        raise ValueError(
            "self reduction candidate references coverage outside the current behavior report"
        )
    if any(
        str(getattr(coverage_by_id[coverage_id], "test_node_id", ""))
        not in test_ids
        for coverage_id in coverage_ids
    ):
        raise ValueError(
            "self reduction candidate coverage is not bound to its exact test nodes"
        )
    covered_dimensions = {
        str(dimension)
        for coverage_id in coverage_ids
        for dimension in getattr(
            coverage_by_id[coverage_id],
            "covered_dimensions",
            (),
        )
        if str(dimension)
    }
    required_dimensions = {"input", "output", "state", "effect", "error"}
    if not required_dimensions <= covered_dimensions:
        raise ValueError(
            "self reduction candidate coverage does not close caller/consumer, state, side-effect, and error parity"
        )
    test_by_id = {
        str(row.node_id): row for row in bundle.test_inventory.nodes
    }
    if set(test_ids) - set(test_by_id):
        raise ValueError(
            "self reduction candidate references tests outside the current inventory"
        )
    required_test_ids = {
        str(value)
        for value in getattr(bundle.test_inventory, "required_node_ids", ())
        if str(value)
    }
    if set(test_ids) - required_test_ids:
        raise ValueError(
            "self reduction candidate tests are not exact required current test nodes"
        )
    pytest_nodeids = tuple(
        sorted(
            {
                str(getattr(test_by_id[test_id], "pytest_nodeid", ""))
                for test_id in test_ids
                if str(getattr(test_by_id[test_id], "pytest_nodeid", ""))
            }
        )
    )
    if len(pytest_nodeids) != len(test_ids):
        raise ValueError(
            "self reduction candidate tests lack exact executable pytest node ids"
        )
    test_paths = tuple(
        sorted({str(test_by_id[test_id].path) for test_id in test_ids})
    )
    _candidate_semantic_bindings(
        bundle,
        candidate,
        test_ids=test_ids,
        coverage_ids=coverage_ids,
    )
    return test_ids, coverage_ids, pytest_nodeids, test_paths


def _proof_input_paths(
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
) -> tuple[str, ...]:
    surface_by_id = {
        str(row.surface_id): row for row in bundle.inventory.surfaces
    }
    member_ids = tuple(candidate.metadata.get("member_ids", ()))
    missing = sorted(set(member_ids) - set(surface_by_id))
    if missing:
        raise ValueError(
            "self reduction candidate members are absent from the current inventory: "
            + ", ".join(missing)
        )
    _, _, _, test_paths = _proof_test_details(bundle, candidate)
    required_surface_ids = set(bundle.inventory.required_surface_ids)
    missing_required_surfaces = sorted(required_surface_ids - set(surface_by_id))
    if missing_required_surfaces:
        raise ValueError(
            "self reduction proof managed inputs are missing required surfaces: "
            + ", ".join(missing_required_surfaces)
        )
    required_test_ids = set(bundle.test_inventory.required_node_ids)
    test_by_id = {
        str(row.node_id): row for row in bundle.test_inventory.nodes
    }
    missing_required_tests = sorted(required_test_ids - set(test_by_id))
    if missing_required_tests:
        raise ValueError(
            "self reduction proof managed inputs are missing required tests: "
            + ", ".join(missing_required_tests)
        )
    return tuple(
        sorted(
            {
                *(
                    str(surface_by_id[surface_id].path)
                    for surface_id in required_surface_ids
                    if surface_id in surface_by_id
                ),
                *(
                    str(test_by_id[test_id].path)
                    for test_id in required_test_ids
                ),
                *test_paths,
            }
        )
    )


def _proof_required_obligations(
    proof_payload: dict[str, Any],
) -> tuple[str, ...]:
    return self_reduction_proof_obligation_ids(
        proof_id=str(proof_payload["proof_id"]),
        subject_revision=str(proof_payload["subject_revision"]),
        inventory_fingerprint=str(proof_payload["inventory_fingerprint"]),
        test_inventory_fingerprint=str(
            proof_payload["test_inventory_fingerprint"]
        ),
        candidate_id=str(proof_payload["candidate_id"]),
        candidate_signal=str(proof_payload["candidate_signal"]),
        candidate_fingerprint=str(proof_payload["candidate_fingerprint"]),
        candidate_inventory_fingerprint=str(
            proof_payload["candidate_inventory_fingerprint"]
        ),
        member_ids=tuple(proof_payload["member_ids"]),
        source_signal_ids=tuple(proof_payload["source_signal_ids"]),
        caller_consumer_ids=tuple(proof_payload["caller_consumer_ids"]),
        public_entrypoint_ids=tuple(proof_payload["public_entrypoint_ids"]),
        proof_status=str(proof_payload["proof_status"]),
        observable_contract_fingerprint=str(
            proof_payload["observable_contract_fingerprint"]
        ),
        test_evidence_ids=tuple(proof_payload["test_evidence_ids"]),
        coverage_ids=tuple(proof_payload["coverage_ids"]),
        parity_obligation_ids=SELF_REDUCTION_PARITY_OBLIGATION_IDS,
        public_facade_binding=proof_payload.get("public_facade_binding"),
    )


def _execution_subject(
    *,
    role: str,
    pytest_nodeids: tuple[str, ...],
    runtime_surfaces: tuple[dict[str, Any], ...] = (),
    oracle_checks: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    result_schema = (
        SELF_REDUCTION_TEST_EXECUTION_SCHEMA
        if role == "test"
        else SELF_REDUCTION_PARITY_EXECUTION_SCHEMA
    )
    payload = {
        "schema_version": "flowguard.self_reduction_execution_subject.v1",
        "result_schema_version": result_schema,
        "role": role,
        "pytest_nodeids": list(pytest_nodeids),
        "runtime_surfaces": [dict(row) for row in runtime_surfaces],
        "oracle_checks": [dict(row) for row in oracle_checks],
    }
    payload["subject_fingerprint"] = fingerprint_value(payload)
    return payload


def _encoded_execution_subject(subject: dict[str, Any]) -> str:
    canonical = json.dumps(
        subject,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(canonical).decode("ascii")


def _proof_execution_subjects(
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
) -> tuple[dict[str, Any], dict[str, Any]]:
    test_ids, coverage_ids, pytest_nodeids, _ = _proof_test_details(bundle, candidate)
    bindings = _candidate_semantic_bindings(
        bundle,
        candidate,
        test_ids=test_ids,
        coverage_ids=coverage_ids,
    )
    surface_by_id = {
        str(getattr(row, "surface_id", "")): row
        for row in bundle.inventory.surfaces
        if str(getattr(row, "surface_id", ""))
    }
    observable = _resolved_candidate_observable_contract(bundle, candidate)
    runtime_surface_ids = {
        str(value)
        for value in candidate.metadata.get("member_ids", ())
        if str(value)
    }
    runtime_surface_ids.update(
        str(value)
        for value in candidate.affected_public_entrypoints
        if str(value)
    )
    runtime_surface_ids.update(
        str(value)
        for value in observable.get("caller_consumer_ids", ())
        if str(value)
    )
    runtime_surface_ids.update(
        str(row["behavior_owner_surface_id"]) for row in bindings
    )
    missing_surfaces = tuple(sorted(runtime_surface_ids - set(surface_by_id)))
    if missing_surfaces:
        raise ValueError(
            "self reduction parity references runtime surfaces outside the current inventory: "
            + ", ".join(missing_surfaces)
        )
    runtime_surfaces: list[dict[str, Any]] = []
    for surface_id in sorted(runtime_surface_ids):
        surface = surface_by_id[surface_id]
        line_start = int(getattr(surface, "line_start", 0))
        line_end = int(getattr(surface, "line_end", 0))
        if line_start < 1 or line_end < line_start:
            raise ValueError(
                "self reduction parity surface has no exact executable source range"
            )
        runtime_surfaces.append(
            {
                "surface_id": surface_id,
                "path": str(getattr(surface, "path", "")),
                "line_start": line_start,
                "line_end": line_end,
                "structure_fingerprint": str(
                    getattr(surface, "structure_fingerprint", "")
                ),
            }
        )
    test_by_id = {
        str(getattr(row, "node_id", "")): row
        for row in bundle.test_inventory.nodes
    }
    oracle_checks: list[dict[str, Any]] = []
    for binding in bindings:
        test = test_by_id[str(binding["test_node_id"])]
        line_start = int(binding["assertion_line_start"])
        line_end = int(binding["assertion_line_end"])
        if line_start < 1 or line_end < line_start:
            raise ValueError(
                "self reduction parity oracle has no exact executable assertion range"
            )
        oracle_checks.append(
            {
                **binding,
                "path": str(getattr(test, "path", "")),
                "line_start": line_start,
                "line_end": line_end,
            }
        )
    return (
        _execution_subject(role="test", pytest_nodeids=pytest_nodeids),
        _execution_subject(
            role="parity",
            pytest_nodeids=pytest_nodeids,
            runtime_surfaces=tuple(runtime_surfaces),
            oracle_checks=tuple(oracle_checks),
        ),
    )


def _proof_contracts(
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
    proof_payload: dict[str, Any],
) -> tuple[ValidationOwnerContract, ValidationOwnerContract, ValidationOwnerContract]:
    test_ids, coverage_ids, pytest_nodeids, _ = _proof_test_details(bundle, candidate)
    test_subject, parity_subject = _proof_execution_subjects(bundle, candidate)
    paths = _proof_input_paths(bundle, candidate)
    test_owner_id, parity_owner_id, aggregate_owner_id = _proof_owner_ids(
        proof_payload
    )
    common_projected = self_reduction_proof_projected_inputs(
        subject_revision=str(proof_payload["subject_revision"]),
        inventory_fingerprint=str(proof_payload["inventory_fingerprint"]),
        test_inventory_fingerprint=str(
            proof_payload["test_inventory_fingerprint"]
        ),
        proof_payload=proof_payload,
    )
    direct_python = Path(sys.base_prefix) / (
        "python.exe" if sys.platform == "win32" else "bin/python"
    )
    python_executable = str(
        direct_python if direct_python.is_file() else Path(sys.executable)
    )
    test_command = (
        python_executable,
        "-c",
        _PYTEST_PROOF_RUNNER_SOURCE,
        _encoded_execution_subject(test_subject),
    )
    parity_command = (
        python_executable,
        "-c",
        _PYTEST_PROOF_RUNNER_SOURCE,
        _encoded_execution_subject(parity_subject),
    )
    test_obligations = tuple(
        sorted(
            {
                _proof_obligation("candidate_test_node", value)
                for value in test_ids
            }
            | {
                _proof_obligation("candidate_coverage", value)
                for value in coverage_ids
            }
            | {
                _proof_obligation(
                    "candidate_observable_contract",
                    proof_payload["observable_contract_fingerprint"],
                )
            }
        )
    )
    parity_obligations = tuple(
        sorted(
            {
                _proof_obligation("candidate_parity", value)
                for value in SELF_REDUCTION_PARITY_OBLIGATION_IDS
            }
            | {
                _proof_obligation(
                    "candidate_observable_contract",
                    proof_payload["observable_contract_fingerprint"],
                )
            }
        )
    )
    test_contract = ValidationOwnerContract(
        owner_id=test_owner_id,
        command=test_command,
        input_patterns=paths,
        obligation_ids=test_obligations,
        projected_inputs=tuple(
            sorted(
                (*common_projected, (
                    "self-reduction:child-role",
                    fingerprint_value("test"),
                ), (
                    "self-reduction:execution-subject",
                    str(test_subject["subject_fingerprint"]),
                ))
            )
        ),
    )
    parity_contract = ValidationOwnerContract(
        owner_id=parity_owner_id,
        command=parity_command,
        input_patterns=paths,
        obligation_ids=parity_obligations,
        projected_inputs=tuple(
            sorted(
                (*common_projected, (
                    "self-reduction:child-role",
                    fingerprint_value("parity"),
                ), (
                    "self-reduction:execution-subject",
                    str(parity_subject["subject_fingerprint"]),
                ))
            )
        ),
    )
    aggregate_contract = ValidationOwnerContract(
        owner_id=aggregate_owner_id,
        command=(
            "flowguard-internal",
            "compose-self-reduction-proof",
            aggregate_owner_id,
        ),
        input_patterns=paths,
        obligation_ids=_proof_required_obligations(proof_payload),
        projected_inputs=tuple(
            sorted(
                (*common_projected, (
                    "self-reduction:child-role",
                    fingerprint_value("aggregate"),
                ))
            )
        ),
        dependency_owner_ids=(test_owner_id, parity_owner_id),
    )
    return test_contract, parity_contract, aggregate_contract


def _leaf_evidence_contexts(
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
    proof_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    test_ids, coverage_ids, pytest_nodeids, _ = _proof_test_details(bundle, candidate)
    test_subject, parity_subject = _proof_execution_subjects(bundle, candidate)
    common = {
        "proof_fingerprint": fingerprint_value(proof_payload),
        "candidate_id": candidate.candidate_id,
        "observable_contract_fingerprint": (
            _candidate_binding(candidate).observable_contract_fingerprint
        ),
    }
    return (
        {
            "schema_version": SELF_REDUCTION_TEST_CHILD_SCHEMA,
            **common,
            "test_node_ids": list(test_ids),
            "coverage_ids": list(coverage_ids),
            "pytest_nodeids": list(pytest_nodeids),
            "execution_subject_fingerprint": test_subject[
                "subject_fingerprint"
            ],
        },
        {
            "schema_version": SELF_REDUCTION_PARITY_CHILD_SCHEMA,
            **common,
            "test_node_ids": list(test_ids),
            "coverage_ids": list(coverage_ids),
            "parity_obligation_ids": list(SELF_REDUCTION_PARITY_OBLIGATION_IDS),
            "observable_contract": _resolved_candidate_observable_contract(
                bundle,
                candidate,
            ),
            "execution_subject_fingerprint": parity_subject[
                "subject_fingerprint"
            ],
        },
    )


def _aggregate_evidence_context(
    proof_payload: dict[str, Any],
    test_receipt: EvidenceReceipt,
    parity_receipt: EvidenceReceipt,
) -> dict[str, Any]:
    return {
        "schema_version": SELF_REDUCTION_AGGREGATE_SCHEMA,
        "self_reduction_proof": proof_payload,
        "child_roles": {
            "test": test_receipt.receipt_id,
            "parity": parity_receipt.receipt_id,
        },
    }


def _canonical_owner_proof_payload(
    receipt_root: str | Path,
    receipt: EvidenceReceipt,
) -> dict[str, Any]:
    root_path = Path(receipt_root)
    relative = str(receipt.metadata.get("proof_relpath", ""))
    if not relative:
        raise ValueError("canonical owner proof has no proof_relpath")
    proof_path = _confined_regular_file(
        root_path,
        relative,
        missing_message=(
            "canonical owner proof path is missing or escapes its store"
        ),
    )
    try:
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("canonical owner proof payload cannot be read") from exc
    if not isinstance(payload, dict):
        raise ValueError("canonical owner proof payload must be an object")
    return payload


def _load_canonical_receipt(
    receipt_id: str,
    repository_root: Path,
    receipt_root: Path,
) -> EvidenceReceipt:
    path = receipt_path(
        receipt_id,
        repository_root,
        output_directory=receipt_root,
    )
    _assert_non_reparse_components(receipt_root, path)
    if not path.is_file() or path.resolve(strict=True) != path:
        raise ValueError(
            "canonical validation-owner receipt is missing or traverses a reparse path"
        )
    return load_evidence_receipt(
        receipt_id,
        repository_root,
        output_directory=receipt_root,
    )


def _validate_semantic_execution_result(
    result: dict[str, Any],
    subject: dict[str, Any],
) -> None:
    expected_fields = {
        "schema_version",
        "role",
        "subject_fingerprint",
        "requested_nodeids",
        "collected_nodeids",
        "deselected_nodeids",
        "missing_nodeids",
        "unrelated_nodeids",
        "outcomes",
        "counts",
        "runtime_surface_results",
        "oracle_results",
        "pytest_exit_code",
        "pytest_stdout_fingerprint",
        "pytest_stderr_fingerprint",
        "ok",
    }
    if set(result) != expected_fields:
        raise ValueError(
            "self reduction semantic execution result has a non-current shape"
        )
    if (
        result.get("schema_version") != subject.get("result_schema_version")
        or result.get("role") != subject.get("role")
        or result.get("subject_fingerprint")
        != subject.get("subject_fingerprint")
        or result.get("pytest_exit_code") != 0
        or result.get("ok") is not True
    ):
        raise ValueError(
            "self reduction semantic execution result does not bind its exact subject"
        )
    requested = tuple(str(value) for value in result["requested_nodeids"])
    expected_requested = tuple(str(value) for value in subject["pytest_nodeids"])
    collected = tuple(str(value) for value in result["collected_nodeids"])
    if (
        requested != expected_requested
        or not requested
        or not collected
        or len(set(collected)) != len(collected)
        or result["deselected_nodeids"] != []
        or result["missing_nodeids"] != []
        or result["unrelated_nodeids"] != []
        or any(
            not any(
                nodeid == item or nodeid.startswith(item + "[")
                for nodeid in collected
            )
            for item in requested
        )
        or any(
            not any(
                nodeid == item or nodeid.startswith(item + "[")
                for item in requested
            )
            for nodeid in collected
        )
    ):
        raise ValueError(
            "self reduction candidate tests were missing, deselected, or unrelated"
        )
    outcomes = result["outcomes"]
    counts = result["counts"]
    if (
        not isinstance(outcomes, dict)
        or set(outcomes) != set(collected)
        or any(value != "passed" for value in outcomes.values())
        or not isinstance(counts, dict)
        or set(counts)
        != {"passed", "failed", "skipped", "xfailed", "xpassed", "not_passed"}
        or counts.get("passed") != len(collected)
        or any(
            counts.get(name) != 0
            for name in ("failed", "skipped", "xfailed", "xpassed", "not_passed")
        )
    ):
        raise ValueError(
            "self reduction candidate tests did not all reach a real pass"
        )
    expected_surfaces = {
        str(row["surface_id"])
        for row in subject.get("runtime_surfaces", ())
    }
    surface_results = result["runtime_surface_results"]
    if (
        not isinstance(surface_results, list)
        or any(
            not isinstance(row, dict)
            or set(row) != {"surface_id", "executed"}
            for row in surface_results
        )
        or {str(row["surface_id"]) for row in surface_results}
        != expected_surfaces
        or len(surface_results) != len(expected_surfaces)
        or any(row["executed"] is not True for row in surface_results)
    ):
        raise ValueError(
            "self reduction parity did not execute every bound code surface"
        )
    expected_oracles = {
        (
            str(row["coverage_id"]),
            str(row["member_id"]),
            str(row["dimension"]),
            str(row["assertion_id"]),
        )
        for row in subject.get("oracle_checks", ())
    }
    oracle_results = result["oracle_results"]
    if (
        not isinstance(oracle_results, list)
        or any(
            not isinstance(row, dict)
            or set(row)
            != {
                "coverage_id",
                "member_id",
                "dimension",
                "assertion_id",
                "executed",
            }
            for row in oracle_results
        )
        or {
            (
                str(row["coverage_id"]),
                str(row["member_id"]),
                str(row["dimension"]),
                str(row["assertion_id"]),
            )
            for row in oracle_results
        }
        != expected_oracles
        or len(oracle_results) != len(expected_oracles)
        or any(row["executed"] is not True for row in oracle_results)
    ):
        raise ValueError(
            "self reduction parity did not execute every bound behavior oracle"
        )
    if not all(
        isinstance(result.get(name), str) and result.get(name)
        for name in ("pytest_stdout_fingerprint", "pytest_stderr_fingerprint")
    ):
        raise ValueError(
            "self reduction execution is missing captured pytest output identities"
        )


def _semantic_result_stdout(result: dict[str, Any]) -> str:
    return (
        _SELF_REDUCTION_RESULT_MARKER
        + json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )


def _parse_semantic_execution_stdout(
    stdout: str,
    subject: dict[str, Any],
) -> dict[str, Any]:
    if stdout.count("\n") != 1 or not stdout.endswith("\n"):
        raise ValueError(
            "self reduction proof command emitted output outside its canonical result"
        )
    line = stdout[:-1]
    if not line.startswith(_SELF_REDUCTION_RESULT_MARKER):
        raise ValueError(
            "self reduction proof command emitted no canonical semantic result"
        )
    try:
        result = json.loads(line[len(_SELF_REDUCTION_RESULT_MARKER) :])
    except json.JSONDecodeError as exc:
        raise ValueError(
            "self reduction proof command emitted malformed semantic evidence"
        ) from exc
    if not isinstance(result, dict):
        raise ValueError("self reduction semantic execution result must be an object")
    _validate_semantic_execution_result(result, subject)
    if stdout != _semantic_result_stdout(result):
        raise ValueError(
            "self reduction semantic execution result is not canonically serialized"
        )
    return result


def _verified_leaf_execution(
    receipt_root: Path,
    receipt: EvidenceReceipt,
    expected_context: dict[str, Any],
    expected_subject: dict[str, Any],
) -> str:
    if receipt.required_child_receipts or receipt.consumed_child_receipts:
        raise ValueError("self reduction proof child must be a leaf owner receipt")
    payload = _canonical_owner_proof_payload(receipt_root, receipt)
    child = payload.get("child")
    if not isinstance(child, dict) or not isinstance(child.get("payload"), dict):
        raise ValueError("canonical owner proof has no typed child payload")
    child_payload = dict(child["payload"])
    execution = child_payload.pop("supervised_execution", None)
    semantic_result = child_payload.pop("execution_result", None)
    if fingerprint_value(child_payload) != fingerprint_value(expected_context):
        raise ValueError(
            "self reduction child does not bind the exact candidate evidence context"
        )
    if not isinstance(execution, dict):
        raise ValueError("self reduction child has no supervised execution evidence")
    if (
        execution.get("schema_version") != VALIDATION_OWNER_EXECUTION_SCHEMA
        or execution.get("exit_code") != 0
        or execution.get("terminal_reason") != "process_exit"
        or execution.get("timed_out") is not False
        or execution.get("cancelled") is not False
        or execution.get("interrupted") is not False
        or execution.get("cleanup_confirmed") is not True
        or execution.get("root_process_running") is not False
        or execution.get("containment_query_succeeded") is not True
        or execution.get("descendant_process_ids") != []
        or not str(execution.get("episode_token", ""))
    ):
        raise ValueError(
            "self reduction child command was not a clean supervised terminal pass"
        )
    if not isinstance(semantic_result, dict):
        raise ValueError(
            "self reduction child has no typed semantic execution result"
        )
    _validate_semantic_execution_result(semantic_result, expected_subject)
    if (
        execution.get("stdout_fingerprint")
        != fingerprint_value(_semantic_result_stdout(semantic_result))
        or execution.get("stderr_fingerprint") != fingerprint_value("")
    ):
        raise ValueError(
            "self reduction semantic result is not bound to the supervised process output"
        )
    return str(execution["episode_token"])


def _derive_current_external_commitment_bindings(
    root: str | Path,
    bundle: FlowGuardSelfBlueprintBundle,
) -> dict[str, tuple[Mapping[str, Any], ...]]:
    """Bind reviewed BCL promises to their exact current blueprint owner once."""

    root_path = _resolved_repository_root(root)
    ledger_path = _confined_regular_file(
        root_path,
        _BEHAVIOR_LEDGER_RELATIVE,
        missing_message=(
            "self reduction necessity review requires the canonical current "
            "behavior ledger"
        ),
    )
    ledger = load_behavior_commitment_ledger(ledger_path)
    ledger_review = review_behavior_commitment_ledger(
        ledger,
        project_root=root_path,
    )
    if not ledger_review.ok:
        raise ValueError(
            "self reduction necessity review requires a fully current behavior ledger"
        )
    ledger_fingerprint = behavior_commitment_ledger_fingerprint(ledger)
    review_fingerprint = fingerprint_value(
        {
            "ledger_fingerprint": ledger_fingerprint,
            "review": ledger_review.to_dict(),
        }
    )
    covered_commitment_ids = set(ledger_review.covered_commitment_ids)

    owner_contract_ids_by_model_element: dict[str, set[str]] = {}
    for contract in getattr(bundle.behavior_report, "contracts", ()):
        if not bool(getattr(contract, "accepted", False)):
            continue
        model_element_id = str(getattr(contract, "model_element_id", ""))
        owner_contract_id = str(getattr(contract, "owner_contract_id", ""))
        if model_element_id and owner_contract_id:
            owner_contract_ids_by_model_element.setdefault(
                model_element_id,
                set(),
            ).add(owner_contract_id)

    implementation_bindings_by_model_element: dict[str, list[Any]] = {}
    for binding in getattr(bundle.binding_report, "bindings", ()):
        model_element_id = str(getattr(binding, "model_element_id", ""))
        if model_element_id:
            implementation_bindings_by_model_element.setdefault(
                model_element_id,
                [],
            ).append(binding)

    bindings: dict[str, list[Mapping[str, Any]]] = {}
    for commitment in ledger.commitments:
        if not commitment.active_external_commitment():
            continue
        commitment_id = str(commitment.commitment_id)
        model_path = str(commitment.primary_owner_model_id).replace("\\", "/")
        model_element_id = f"model-obligation:{model_path}"
        owner_contract_ids = owner_contract_ids_by_model_element.get(
            model_element_id,
            set(),
        )
        if not owner_contract_ids:
            continue
        if len(owner_contract_ids) != 1:
            raise ValueError(
                "one active behavior commitment maps to ambiguous current blueprint owners"
            )
        owner_contract_id = next(iter(owner_contract_ids))
        evidence = commitment.evidence
        if (
            commitment_id not in covered_commitment_ids
            or commitment.model_sync_state != BCL_MODEL_SYNC_OWNER_CURRENT
            or not evidence.has_current_pass()
            or not evidence.has_required_links()
            or owner_contract_id not in set(evidence.code_contract_ids)
        ):
            raise ValueError(
                "one active behavior commitment lacks an exact current "
                "model/code/test binding"
            )
        declared_bindings: list[tuple[Any, str, tuple[str, ...]]] = []
        evidence_code_contract_ids = set(evidence.code_contract_ids)
        evidence_test_ids = tuple(sorted(set(evidence.test_evidence_ids)))
        for implementation_binding in implementation_bindings_by_model_element.get(
            model_element_id,
            (),
        ):
            binding_id = str(getattr(implementation_binding, "binding_id", ""))
            implementation_surface_id = str(
                getattr(implementation_binding, "implementation_surface_id", "")
            )
            binding_owner_contract_id = str(
                getattr(implementation_binding, "owner_contract_id", "")
            )
            binding_test_ids = tuple(
                sorted(
                    {
                        str(value)
                        for value in getattr(
                            implementation_binding,
                            "test_evidence_ids",
                            (),
                        )
                        if str(value)
                    }
                )
            )
            surface_code_contract_id = "code-contract:" + binding_id
            if surface_code_contract_id not in evidence_code_contract_ids:
                continue
            if (
                not binding_id
                or not implementation_surface_id
                or binding_owner_contract_id != owner_contract_id
                or binding_test_ids != evidence_test_ids
            ):
                raise ValueError(
                    "one active behavior commitment declares a stale or foreign "
                    "implementation-surface/code/test binding"
                )
            declared_bindings.append(
                (
                    implementation_binding,
                    surface_code_contract_id,
                    binding_test_ids,
                )
            )
        if not declared_bindings:
            # A current external commitment remains valid for its ordinary BCL
            # purpose without becoming a no-caller necessity witness.  Only a
            # commitment that explicitly names one exact surface contract may
            # authorize that surface in architecture reduction.
            continue
        (
            behavior_plane,
            actor_kind,
            actor,
            trigger,
            preconditions,
            terminal_or_result,
            failure_boundary,
            state_writes,
            side_effects,
        ) = commitment.exact_external_semantics_key()
        semantics = {
            "behavior_plane": behavior_plane,
            "actor_kind": actor_kind,
            "actor": actor,
            "trigger": trigger,
            "preconditions": list(preconditions),
            "terminal_or_result": terminal_or_result,
            "failure_boundary": failure_boundary,
            "state_writes": list(state_writes),
            "side_effects": list(side_effects),
        }
        for (
            implementation_binding,
            surface_code_contract_id,
            binding_test_ids,
        ) in declared_bindings:
            binding_id = str(implementation_binding.binding_id)
            implementation_surface_id = str(
                implementation_binding.implementation_surface_id
            )
            binding_seed = {
                "ledger_fingerprint": ledger_fingerprint,
                "review_fingerprint": review_fingerprint,
                "commitment_id": commitment_id,
                "model_element_id": model_element_id,
                "owner_contract_id": owner_contract_id,
                "implementation_surface_id": implementation_surface_id,
                "binding_id": binding_id,
                "surface_code_contract_id": surface_code_contract_id,
                "model_obligation_ids": list(evidence.model_obligation_ids),
                "code_contract_ids": list(evidence.code_contract_ids),
                "test_evidence_ids": list(binding_test_ids),
                "semantics": semantics,
            }
            bindings.setdefault(model_element_id, []).append(
                {
                    "commitment_id": commitment_id,
                    "review_fingerprint": review_fingerprint,
                    "model_element_id": model_element_id,
                    "owner_contract_id": owner_contract_id,
                    "implementation_surface_id": implementation_surface_id,
                    "binding_id": binding_id,
                    "code_contract_ids": tuple(evidence.code_contract_ids),
                    "test_evidence_ids": binding_test_ids,
                    "binding_fingerprint": fingerprint_value(binding_seed),
                    "semantics": semantics,
                }
            )
    return {
        model_element_id: tuple(
            sorted(
                rows,
                key=lambda row: (
                    str(row["commitment_id"]),
                    str(row["implementation_surface_id"]),
                ),
            )
        )
        for model_element_id, rows in sorted(bindings.items())
    }


def _derive_public_facade_binding(
    root: str | Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
) -> dict[str, Any]:
    """Derive facade authority from current code/model/BCL owners only."""

    root_path = _resolved_repository_root(root)
    ledger_path = _confined_regular_file(
        root_path,
        _BEHAVIOR_LEDGER_RELATIVE,
        missing_message=(
            "public-facade proof requires the canonical current behavior ledger"
        ),
    )
    ledger = load_behavior_commitment_ledger(ledger_path)
    ledger_review = review_behavior_commitment_ledger(
        ledger,
        project_root=root_path,
    )
    if not ledger_review.ok:
        raise ValueError(
            "public-facade proof requires a fully current behavior ledger"
        )
    ledger_fingerprint = behavior_commitment_ledger_fingerprint(ledger)
    public_ids = tuple(
        sorted(
            {
                str(value)
                for value in candidate.affected_public_entrypoints
                if str(value)
            }
        )
    )
    if len(public_ids) != 1:
        raise ValueError(
            "public-facade proof requires one exact affected public entrypoint"
        )
    inventory_surface_by_id = {
        str(getattr(row, "surface_id", "")): row
        for row in bundle.inventory.surfaces
        if str(getattr(row, "surface_id", ""))
    }
    public_surface = inventory_surface_by_id.get(public_ids[0])
    if (
        public_surface is None
        or public_ids[0]
        not in set(getattr(bundle.inventory, "required_surface_ids", ()))
        or (
            "entrypoint" not in tuple(getattr(public_surface, "roles", ()))
            and str(getattr(public_surface, "surface_kind", "")) != "entrypoint"
        )
    ):
        raise ValueError(
            "public-facade proof entrypoint is not a required current code entrypoint"
        )
    public_path = str(getattr(public_surface, "path", "")).replace("\\", "/")
    public_symbol = str(getattr(public_surface, "symbol", public_ids[0]))

    def source_matches_public(row: Any) -> bool:
        source_parts = tuple(
            part.strip().replace("\\", "/")
            for part in str(row.source_ref).split(";")
            if part.strip()
        )
        path_bound = any(
            part == public_path
            or part.startswith(public_path + "#")
            or part.startswith(public_path + ":")
            for part in source_parts
        )
        if not public_path or not public_symbol or not path_bound:
            return False
        if str(getattr(row, "native_artifact_id", "")) == public_ids[0]:
            return True
        return bool(
            set(source_parts)
            & {
                f"{public_path}#{public_symbol}",
                f"{public_path}:{public_symbol}",
                public_ids[0],
            }
        )

    matching_source_rows = tuple(
        row
        for row in ledger.source_surfaces
        if source_matches_public(row)
        and row.in_scope
        and row.freshness_state == "current"
        and row.coverage_disposition == BCL_DISPOSITION_MODELED
        and row.source_authority_role
        in {BCL_SOURCE_AUTHORITY_NORMATIVE, BCL_SOURCE_AUTHORITY_OBSERVED}
        and row.declared_semantics_fingerprint
        and row.delegates_to_primary_path
        and row.primary_path_id
        and len(row.commitment_ids) == 1
        and len(row.business_intent_ids) == 1
        and row.content_fingerprint
        and row.discovery_evidence_ids
        and (
            not ledger.source_inventory_revision
            or row.inventory_revision == ledger.source_inventory_revision
        )
    )
    if len(matching_source_rows) != 1:
        raise ValueError(
            "public-facade code has no unique current delegated behavior-ledger source"
        )
    source = matching_source_rows[0]
    commitment_by_id = {
        str(row.commitment_id): row for row in ledger.commitments
    }
    commitment = commitment_by_id.get(source.commitment_ids[0])
    if commitment is None:
        raise ValueError(
            "public-facade source references no current behavior commitment"
        )
    behavior_contracts = tuple(getattr(bundle.behavior_report, "contracts", ()))
    direct = tuple(
        row
        for row in behavior_contracts
        if str(getattr(row, "implementation_surface_id", "")) == public_ids[0]
    )
    delegated_relations = tuple(
        row
        for row in getattr(bundle.behavior_report, "supporting_relations", ())
        if str(getattr(row, "supporting_surface_id", "")) == public_ids[0]
        and str(getattr(row, "relation_kind", "")) == "delegates"
    )
    if direct or len(delegated_relations) != 1:
        raise ValueError(
            "public-facade code/model binding is not delegation-only"
        )
    relation = delegated_relations[0]
    owner_contracts = tuple(
        row
        for row in behavior_contracts
        if str(getattr(row, "behavior_block_id", ""))
        == str(getattr(relation, "behavior_block_id", ""))
    )
    if len(owner_contracts) != 1:
        raise ValueError(
            "public-facade delegation has no unique behavior/code owner"
        )
    owner_contract = owner_contracts[0]
    owner_code_contract_id = str(
        getattr(owner_contract, "owner_contract_id", "")
    )
    path_authority = commitment.path_authority
    evidence = commitment.evidence
    owner_surface = inventory_surface_by_id.get(
        str(getattr(owner_contract, "implementation_surface_id", ""))
    )
    if (
        commitment.business_intent_id != source.business_intent_ids[0]
        or commitment.commitment_id != source.commitment_ids[0]
        or source.surface_id not in commitment.source_surface_ids
        or not commitment.in_scope
        or not commitment.active_external_commitment()
        or commitment.replacement_state != "active"
        or commitment.model_sync_state != BCL_MODEL_SYNC_OWNER_CURRENT
        or commitment.surface_delegation_only
        or not bool(getattr(owner_contract, "accepted", False))
        or owner_surface is None
        or str(getattr(owner_contract, "source_fingerprint", ""))
        != str(getattr(owner_surface, "content_fingerprint", ""))
        or str(getattr(relation, "evidence_id", "")) == ""
        or str(getattr(relation, "evidence_fingerprint", ""))
        != str(getattr(public_surface, "structure_fingerprint", ""))
        or not evidence.has_current_pass()
        or not evidence.has_required_links()
        or owner_code_contract_id not in set(evidence.code_contract_ids)
        or not path_authority.path_sensitive
        or not path_authority.ppa_passed()
        or path_authority.business_intent_id != commitment.business_intent_id
        or path_authority.behavior_commitment_id != commitment.commitment_id
        or path_authority.primary_path_id != source.primary_path_id
    ):
        raise ValueError(
            "public-facade behavior commitment lacks one current model/code/path authority"
        )
    subject_revision = str(
        getattr(getattr(bundle.inventory, "boundary", None), "subject_revision", "")
    )
    inventory_fingerprint = str(
        getattr(bundle.inventory, "inventory_fingerprint", "")
    )
    behavior_report_fingerprint = str(
        getattr(bundle.behavior_report, "fingerprint", "")
    )
    candidate_id = str(getattr(candidate, "candidate_id", ""))
    if not all(
        (
            subject_revision,
            inventory_fingerprint,
            behavior_report_fingerprint,
            candidate_id,
            owner_code_contract_id,
            str(getattr(public_surface, "content_fingerprint", "")),
            str(getattr(public_surface, "structure_fingerprint", "")),
        )
    ):
        raise ValueError(
            "public-facade proof lacks exact current bundle/code identities"
        )
    evidence_payload = {
        "subject_revision": subject_revision,
        "inventory_fingerprint": inventory_fingerprint,
        "behavior_report_fingerprint": behavior_report_fingerprint,
        "candidate_id": candidate_id,
        "public_surface": {
            "surface_id": public_ids[0],
            "path": public_path,
            "symbol": public_symbol,
            "content_fingerprint": str(
                getattr(public_surface, "content_fingerprint", "")
            ),
            "structure_fingerprint": str(
                getattr(public_surface, "structure_fingerprint", "")
            ),
        },
        "ledger_fingerprint": ledger_fingerprint,
        "source_surface": source.to_dict(),
        "supporting_relation": relation.to_dict(),
        "owner_contract": owner_contract.to_dict(),
        "behavior_commitment": commitment.to_dict(),
    }
    evidence_id = (
        "public-facade-delegation:"
        + fingerprint_value(evidence_payload).split(":", 1)[1]
    )
    return {
        "public_facade_delegation_evidence_id": evidence_id,
        "business_intent_id": commitment.business_intent_id,
        "behavior_commitment_id": commitment.commitment_id,
        "primary_path_id": source.primary_path_id,
        "owner_code_contract_id": owner_code_contract_id,
        "delegates_to_code_contract_id": owner_code_contract_id,
        "delegates_to_primary_path_id": source.primary_path_id,
        "delegation_only": True,
        "independent_business_authority": False,
    }


def _self_reduction_proof_field_projection(
    *,
    subject_revision: str,
    inventory_fingerprint: str,
    test_inventory_fingerprint: str,
    candidate_id: str,
    candidate_signal: str,
    candidate_fingerprint: str,
    candidate_inventory_fingerprint: str,
    member_ids: tuple[str, ...],
    source_signal_ids: tuple[str, ...],
    caller_consumer_ids: tuple[str, ...],
    public_entrypoint_ids: tuple[str, ...],
    observable_contract_fingerprint: str,
    test_evidence_ids: tuple[str, ...],
    coverage_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Project the one ordered field set used for proof currentness."""

    return {
        "subject_revision": subject_revision,
        "inventory_fingerprint": inventory_fingerprint,
        "test_inventory_fingerprint": test_inventory_fingerprint,
        "candidate_id": candidate_id,
        "candidate_signal": candidate_signal,
        "candidate_fingerprint": candidate_fingerprint,
        "candidate_inventory_fingerprint": candidate_inventory_fingerprint,
        "member_ids": member_ids,
        "source_signal_ids": source_signal_ids,
        "caller_consumer_ids": caller_consumer_ids,
        "public_entrypoint_ids": public_entrypoint_ids,
        "observable_contract_fingerprint": observable_contract_fingerprint,
        "test_evidence_ids": test_evidence_ids,
        "coverage_ids": coverage_ids,
    }


def _expected_self_reduction_proof_fields(
    root: str | Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
) -> dict[str, Any]:
    binding = _candidate_binding(candidate)
    test_ids, coverage_ids, _, _ = _proof_test_details(bundle, candidate)
    return _self_reduction_proof_field_projection(
        subject_revision=bundle.inventory.boundary.subject_revision,
        inventory_fingerprint=bundle.inventory.inventory_fingerprint,
        test_inventory_fingerprint=bundle.test_inventory.inventory_fingerprint,
        candidate_id=binding.candidate_id,
        candidate_signal=binding.signal,
        candidate_fingerprint=binding.fingerprint,
        candidate_inventory_fingerprint=candidate.inventory_revision,
        member_ids=binding.member_ids,
        source_signal_ids=binding.source_signal_ids,
        caller_consumer_ids=binding.caller_ids,
        public_entrypoint_ids=binding.public_entrypoint_ids,
        observable_contract_fingerprint=binding.observable_contract_fingerprint,
        test_evidence_ids=test_ids,
        coverage_ids=coverage_ids,
    )


def _self_reduction_proof_field_mismatch(
    root: str | Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
    proof: SelfReductionProofRecord,
) -> str | None:
    expected = _expected_self_reduction_proof_fields(root, bundle, candidate)
    observed = _self_reduction_proof_field_projection(
        subject_revision=proof.subject_revision,
        inventory_fingerprint=proof.inventory_fingerprint,
        test_inventory_fingerprint=proof.test_inventory_fingerprint,
        candidate_id=proof.candidate_id,
        candidate_signal=proof.candidate_signal,
        candidate_fingerprint=proof.candidate_fingerprint,
        candidate_inventory_fingerprint=proof.candidate_inventory_fingerprint,
        member_ids=proof.member_ids,
        source_signal_ids=proof.source_signal_ids,
        caller_consumer_ids=proof.caller_consumer_ids,
        public_entrypoint_ids=proof.public_entrypoint_ids,
        observable_contract_fingerprint=proof.observable_contract_fingerprint,
        test_evidence_ids=proof.test_evidence_ids,
        coverage_ids=proof.coverage_ids,
    )
    return next(
        (
            name
            for name, expected_value in expected.items()
            if observed[name] != expected_value
        ),
        None,
    )


def _validate_record_against_candidate(
    root: str | Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
    proof: SelfReductionProofRecord,
) -> None:
    mismatch = _self_reduction_proof_field_mismatch(
        root,
        bundle,
        candidate,
        proof,
    )
    if mismatch is not None:
        raise ValueError(
            f"self reduction proof {mismatch} does not match the current candidate observable contract"
        )
    expected_facade_binding = (
        _derive_public_facade_binding(root, bundle, candidate)
        if proof.proof_status == PROOF_SAFE_BY_PUBLIC_FACADE
        else None
    )
    if proof.public_facade_binding != expected_facade_binding:
        raise ValueError(
            "self reduction proof public-facade authority is not derived from current model/code/ledger owners"
        )


def _self_reduction_proof_payload(
    root: str | Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
    proof_status: str,
) -> dict[str, Any]:
    """Build the one canonical semantic subject used by every proof owner."""

    if proof_status not in {
        PROOF_SAFE_BY_EQUIVALENCE,
        PROOF_SAFE_BY_PUBLIC_FACADE,
    }:
        raise ValueError("self reduction proof status is not contraction-ready")
    binding = _candidate_binding(candidate)
    test_ids, coverage_ids, _, _ = _proof_test_details(bundle, candidate)
    facade_binding = (
        _derive_public_facade_binding(root, bundle, candidate)
        if proof_status == PROOF_SAFE_BY_PUBLIC_FACADE
        else None
    )
    payload: dict[str, Any] = {
        "schema_version": SELF_REDUCTION_PROOF_RECORD_SCHEMA,
        "subject_revision": bundle.inventory.boundary.subject_revision,
        "inventory_fingerprint": bundle.inventory.inventory_fingerprint,
        "test_inventory_fingerprint": (
            bundle.test_inventory.inventory_fingerprint
        ),
        "candidate_id": binding.candidate_id,
        "candidate_signal": binding.signal,
        "candidate_fingerprint": binding.fingerprint,
        "candidate_inventory_fingerprint": candidate.inventory_revision,
        "member_ids": list(binding.member_ids),
        "source_signal_ids": list(binding.source_signal_ids),
        "caller_consumer_ids": list(binding.caller_ids),
        "public_entrypoint_ids": list(binding.public_entrypoint_ids),
        "proof_status": proof_status,
        "observable_contract_fingerprint": (
            binding.observable_contract_fingerprint
        ),
        "test_evidence_ids": list(test_ids),
        "coverage_ids": list(coverage_ids),
        "parity_results": {
            obligation_id: RECEIPT_STATUS_PASS
            for obligation_id in SELF_REDUCTION_PARITY_OBLIGATION_IDS
        },
        "public_facade_binding": facade_binding,
    }
    payload["proof_id"] = _deterministic_self_reduction_proof_id(payload)
    return payload


def _load_verified_leaf(
    root: Path,
    receipt_root: Path,
    current: Any,
    receipt_id: str,
    expected_context: dict[str, Any],
    expected_subject: dict[str, Any],
) -> tuple[EvidenceReceipt, ReceiptVerificationResult, str]:
    expected_canonical = _load_canonical_receipt(
        receipt_id,
        root,
        receipt_root,
    )
    canonical, verification = find_reusable_owner_receipt(
        current,
        root,
        receipt_root,
    )
    if canonical is None or verification is None or not verification.ok:
        raise ValueError(
            "self reduction proof child has no exact-current canonical owner receipt"
        )
    if (
        canonical.receipt_id != receipt_id
        or canonical.fingerprint != expected_canonical.fingerprint
    ):
        raise ValueError(
            "self reduction aggregate references a stale or unrelated child receipt"
        )
    if canonical.subject_kind != OWNER_RECEIPT_KIND:
        raise ValueError("self reduction proof child has the wrong receipt kind")
    episode = _verified_leaf_execution(
        receipt_root,
        canonical,
        expected_context,
        expected_subject,
    )
    return canonical, verification, episode


def _verify_one_proof_record(
    root: Path,
    receipt_root: Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
    proof: SelfReductionProofRecord,
) -> _VerifiedSelfReductionProof:
    _validate_record_against_candidate(root, bundle, candidate, proof)
    proof_payload = proof.canonical_evidence_payload
    contracts = _proof_contracts(bundle, candidate, proof_payload)
    ordered = topological_owner_contracts(contracts)
    currents = {
        contract.owner_id: build_owner_current(
            root,
            contract,
            all_contracts=ordered,
        )
        for contract in ordered
    }
    test_contract, parity_contract, aggregate_contract = contracts
    aggregate = _load_canonical_receipt(
        proof.aggregate_receipt_id,
        root,
        receipt_root,
    )
    assert_validation_owner_receipt_integrity(aggregate)
    if (
        aggregate.subject_kind != OWNER_RECEIPT_KIND
        or aggregate.subject_id != f"validation-owner:{aggregate_contract.owner_id}"
        or aggregate.producer_id != aggregate.subject_id
        or aggregate.claim_scope != OWNER_RECEIPT_SCOPE
        or aggregate.result_status != RECEIPT_STATUS_PASS
        or aggregate.exit_code != 0
        or aggregate.skipped_checks
        or aggregate.blockers
        or len(aggregate.required_child_receipts) != 2
        or len(aggregate.consumed_child_receipts) != 2
    ):
        raise ValueError(
            "self reduction proof requires one canonical child-bound aggregate pass"
        )
    requirement_by_subject = {
        item.subject_id: item for item in aggregate.required_child_receipts
    }
    expected_subjects = {
        f"validation-owner:{test_contract.owner_id}",
        f"validation-owner:{parity_contract.owner_id}",
    }
    if set(requirement_by_subject) != expected_subjects:
        raise ValueError(
            "self reduction aggregate is missing exact test or parity children"
        )
    test_context, parity_context = _leaf_evidence_contexts(
        bundle,
        candidate,
        proof_payload,
    )
    test_subject, parity_subject = _proof_execution_subjects(bundle, candidate)
    test_requirement = requirement_by_subject[
        f"validation-owner:{test_contract.owner_id}"
    ]
    parity_requirement = requirement_by_subject[
        f"validation-owner:{parity_contract.owner_id}"
    ]
    test_receipt, test_verification, test_episode = _load_verified_leaf(
        root,
        receipt_root,
        currents[test_contract.owner_id],
        test_requirement.receipt_id,
        test_context,
        test_subject,
    )
    parity_receipt, parity_verification, parity_episode = _load_verified_leaf(
        root,
        receipt_root,
        currents[parity_contract.owner_id],
        parity_requirement.receipt_id,
        parity_context,
        parity_subject,
    )
    aggregate_payload = _canonical_owner_proof_payload(receipt_root, aggregate)
    expected_aggregate_context = _aggregate_evidence_context(
        proof_payload,
        test_receipt,
        parity_receipt,
    )
    if (
        aggregate_payload.get("schema_version")
        != "flowguard.child_bound_validation_owner_proof.v1"
        or fingerprint_value(aggregate_payload.get("evidence_context"))
        != fingerprint_value(expected_aggregate_context)
    ):
        raise ValueError(
            "self reduction aggregate does not bind the exact candidate and child roles"
        )
    aggregate_context = build_child_bound_owner_receipt_context(
        currents[aggregate_contract.owner_id],
        aggregate,
        root,
        receipt_root,
        child_receipts=(test_receipt, parity_receipt),
        child_verification_results=(test_verification, parity_verification),
    )
    aggregate_verification = verify_evidence_receipt(
        aggregate,
        aggregate_context,
    )
    if not aggregate_verification.ok:
        raise ValueError(
            "self reduction aggregate is stale, blocked, skipped, or not canonical"
        )
    return _VerifiedSelfReductionProof(
        record=proof,
        aggregate_receipt=aggregate,
        aggregate_verification=aggregate_verification,
        child_receipts=(test_receipt, parity_receipt),
        child_verifications=(test_verification, parity_verification),
        owner_contracts=ordered,
        owner_identities=tuple(
            currents[contract.owner_id].owner_identity for contract in ordered
        ),
        episode_tokens=(test_episode, parity_episode),
    )


def _verify_proof_records(
    root: str | Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidates: tuple[ArchitectureReductionCandidate, ...],
    proof_records: tuple[SelfReductionProofRecord, ...],
) -> tuple[_VerifiedSelfReductionProof, ...]:
    if not proof_records:
        return ()
    root_path = _resolved_repository_root(root)
    canonical_root = _canonical_validation_owner_root(root_path)
    candidate_by_id = {row.candidate_id: row for row in candidates}
    verified: list[_VerifiedSelfReductionProof] = []
    uniqueness: dict[str, set[str]] = {
        "receipt_id": set(),
        "receipt_fingerprint": set(),
        "proof_artifact_id": set(),
        "proof_artifact_fingerprint": set(),
        "result_fingerprint": set(),
        "owner_execution_identity": set(),
        "episode_token": set(),
    }
    for proof in proof_records:
        candidate = candidate_by_id.get(proof.candidate_id)
        if candidate is None:
            raise ValueError(
                "self reduction proof references an unknown current candidate"
            )
        item = _verify_one_proof_record(
            root_path,
            canonical_root,
            bundle,
            candidate,
            proof,
        )
        receipt_rows = (item.aggregate_receipt, *item.child_receipts)
        values = {
            "receipt_id": tuple(row.receipt_id for row in receipt_rows),
            "receipt_fingerprint": tuple(row.fingerprint for row in receipt_rows),
            "proof_artifact_id": tuple(row.proof_artifact_id for row in receipt_rows),
            "proof_artifact_fingerprint": tuple(
                row.proof_artifact_fingerprint for row in receipt_rows
            ),
            "result_fingerprint": tuple(
                row.result_fingerprint for row in receipt_rows
            ),
            "owner_execution_identity": item.owner_identities,
            "episode_token": item.episode_tokens,
        }
        for kind, rows in values.items():
            for value in rows:
                if value in uniqueness[kind]:
                    raise ValueError(
                        f"self reduction proof registry reuses {kind} across candidates"
                    )
                uniqueness[kind].add(value)
        verified.append(item)
    return tuple(verified)


def _proof_record_from_canonical_aggregate(
    receipt_root: Path,
    aggregate: EvidenceReceipt,
) -> SelfReductionProofRecord:
    """Rebuild one record directly from the canonical aggregate proof artifact."""

    assert_validation_owner_receipt_integrity(aggregate)
    payload = _canonical_owner_proof_payload(receipt_root, aggregate)
    expected_outer_fields = {
        "schema_version",
        "owner_id",
        "owner_identity",
        "covered_obligations",
        "children",
        "evidence_context",
    }
    if (
        set(payload) != expected_outer_fields
        or payload.get("schema_version")
        != "flowguard.child_bound_validation_owner_proof.v1"
    ):
        raise ValueError(
            "self reduction aggregate proof does not use the current exact schema"
        )
    evidence_context = payload.get("evidence_context")
    if not isinstance(evidence_context, Mapping) or set(evidence_context) != {
        "schema_version",
        "self_reduction_proof",
        "child_roles",
    }:
        raise ValueError(
            "self reduction aggregate evidence context has a non-current shape"
        )
    if evidence_context.get("schema_version") != SELF_REDUCTION_AGGREGATE_SCHEMA:
        raise ValueError("self reduction aggregate evidence schema is stale")
    child_roles = evidence_context.get("child_roles")
    if (
        not isinstance(child_roles, Mapping)
        or set(child_roles) != {"test", "parity"}
        or any(
            not isinstance(value, str) or not value
            for value in child_roles.values()
        )
    ):
        raise ValueError(
            "self reduction aggregate does not declare exact test and parity child roles"
        )
    record = SelfReductionProofRecord.from_canonical_evidence_payload(
        evidence_context.get("self_reduction_proof"),
        aggregate_receipt_id=aggregate.receipt_id,
    )
    expected_subject = f"validation-owner:{record.proof_owner_id}"
    if (
        aggregate.subject_id != expected_subject
        or aggregate.producer_id != expected_subject
        or payload.get("owner_id") != record.proof_owner_id
    ):
        raise ValueError(
            "self reduction aggregate owner does not match its reconstructed proof subject"
        )
    return record


def _proof_record_matches_current_candidate(
    root: str | Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
    record: SelfReductionProofRecord,
) -> bool:
    if _self_reduction_proof_field_mismatch(
        root,
        bundle,
        candidate,
        record,
    ) is not None:
        return False
    expected_facade_binding = (
        _derive_public_facade_binding(root, bundle, candidate)
        if record.proof_status == PROOF_SAFE_BY_PUBLIC_FACADE
        else None
    )
    return record.public_facade_binding == expected_facade_binding


def _discover_current_self_reduction_proofs(
    root: str | Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidates: tuple[ArchitectureReductionCandidate, ...],
) -> tuple[tuple[_VerifiedSelfReductionProof, ...], tuple[str, ...]]:
    """Discover the unique exact-current proof set from the one canonical store."""

    root_path = _resolved_repository_root(root)
    receipt_root = _canonical_validation_owner_root(root_path)
    aggregate_receipts = tuple(
        sorted(
            (
                receipt
                for receipt in list_evidence_receipts(
                    root_path,
                    output_directory=receipt_root,
                )
                if receipt.subject_id.startswith(
                    "validation-owner:self-reduction-aggregate-"
                )
            ),
            key=lambda receipt: receipt.receipt_id,
        )
    )
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    current_records: list[SelfReductionProofRecord] = []
    historical_receipt_ids: list[str] = []
    current_by_candidate_id: dict[str, list[SelfReductionProofRecord]] = {}
    for aggregate in aggregate_receipts:
        record = _proof_record_from_canonical_aggregate(
            receipt_root,
            aggregate,
        )
        candidate = candidate_by_id.get(record.candidate_id)
        if candidate is None or not _proof_record_matches_current_candidate(
            root_path,
            bundle,
            candidate,
            record,
        ):
            historical_receipt_ids.append(aggregate.receipt_id)
            continue
        current_by_candidate_id.setdefault(record.candidate_id, []).append(record)
    ambiguous = tuple(
        sorted(
            candidate_id
            for candidate_id, records in current_by_candidate_id.items()
            if len(records) > 1
        )
    )
    if ambiguous:
        raise ValueError(
            "multiple exact-current self reduction aggregate proofs exist for "
            "candidate(s): " + ", ".join(ambiguous)
        )
    current_records.extend(
        records[0]
        for _, records in sorted(current_by_candidate_id.items())
    )
    return (
        _verify_proof_records(
            root_path,
            bundle,
            candidates,
            tuple(current_records),
        ),
        tuple(sorted(historical_receipt_ids)),
    )


def _recheck_verified_proof_currentness(
    root: str | Path,
    verified_proofs: tuple[_VerifiedSelfReductionProof, ...],
) -> None:
    """Recheck exact proof inputs and stored artifacts without semantic replay."""

    if not verified_proofs:
        return
    root_path = _resolved_repository_root(root)
    receipt_root = _canonical_validation_owner_root(root_path)
    for proof in verified_proofs:
        currents = tuple(
            build_owner_current(
                root_path,
                contract,
                all_contracts=proof.owner_contracts,
            )
            for contract in proof.owner_contracts
        )
        owner_identities = tuple(current.owner_identity for current in currents)
        if owner_identities != proof.owner_identities:
            raise ValueError(
                "self reduction proof owner input identity changed before review publication"
            )
        current_by_subject = {
            f"validation-owner:{current.contract.owner_id}": current
            for current in currents
        }
        expected_receipts = (proof.aggregate_receipt, *proof.child_receipts)
        if set(current_by_subject) != {
            receipt.subject_id for receipt in expected_receipts
        }:
            raise ValueError(
                "self reduction proof owner currentness is incomplete before review publication"
            )
        for expected in expected_receipts:
            canonical = _load_canonical_receipt(
                expected.receipt_id,
                root_path,
                receipt_root,
            )
            if canonical.to_dict() != expected.to_dict():
                raise ValueError(
                    "self reduction proof receipt identity changed before review publication"
                )
            current = current_by_subject[canonical.subject_id]
            if (
                str(canonical.metadata.get("owner_identity", ""))
                != current.owner_identity
            ):
                raise ValueError(
                    "self reduction proof owner identity changed before review publication"
                )
            relative = str(canonical.metadata.get("proof_relpath", ""))
            if not relative:
                raise ValueError(
                    "self reduction proof artifact identity is missing before review publication"
                )
            proof_path = _confined_regular_file(
                receipt_root,
                relative,
                missing_message=(
                    "self reduction proof artifact is missing or escapes its store "
                    "before review publication"
                ),
            )
            proof_fingerprint = (
                "sha256:" + hashlib.sha256(proof_path.read_bytes()).hexdigest()
            )
            if (
                proof_fingerprint != canonical.proof_artifact_fingerprint
                or proof_fingerprint != canonical.result_fingerprint
            ):
                raise ValueError(
                    "self reduction proof artifact identity changed before review publication"
                )


def _reverse_call_alias_index(
    surfaces: tuple[Any, ...],
    *,
    root: str | Path | None = None,
) -> _CanonicalConsumerIndex:
    """Use the blueprint's one canonical call graph for reduction review."""

    return _canonical_consumer_index(surfaces, root=root)


def _indexed_caller_ids(
    members: tuple[Any, ...],
    *,
    call_index: _CanonicalConsumerIndex,
) -> tuple[str, ...]:
    """Return callers only from disambiguated canonical surface-id edges."""

    caller_ids: set[str] = set()
    for member in members:
        caller_ids.update(
            call_index.callers_by_surface_id.get(str(member.surface_id), ())
        )
    return tuple(sorted(caller_ids))


def _indexed_caller_gap_ids(
    members: tuple[Any, ...],
    *,
    call_index: _CanonicalConsumerIndex,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                gap_id
                for member in members
                for gap_id in call_index.gap_ids_by_surface_id.get(
                    str(member.surface_id), ()
                )
            }
        )
    )


@dataclass(frozen=True)
class SelfArchitectureReductionReview:
    self_blueprint_fingerprint: str
    implementation_inventory_fingerprint: str
    behavior_report_fingerprint: str
    reduction_universe: SelfReductionUniverse
    reduction_universe_fingerprint: str
    candidate_inventory_fingerprint: str
    candidate_evidence_neighborhood_catalog: (
        SelfReductionEvidenceNeighborhoodCatalog
    )
    candidate_evidence_neighborhood_catalog_fingerprint: str
    proof_registry_fingerprint: str
    retain_registry_fingerprint: str
    retain_dispositions: tuple[SelfReductionRetainDisposition, ...]
    candidates: tuple[ArchitectureReductionCandidate, ...]
    compatibility_classifications: tuple[CompatibilitySurfaceClassification, ...]
    reduction_report: ArchitectureReductionReport
    denominator_complete: bool
    candidate_review_complete: bool
    step_decision_complete: bool
    candidate_inventory_independent: bool
    audit_accounted: bool
    audit_complete: bool
    action_authorized_candidate_ids: tuple[str, ...]
    cleanup_release_ready: bool
    necessity_gap_counts_by_kind: tuple[tuple[str, int], ...]
    necessity_gap_examples_by_kind: tuple[tuple[str, tuple[str, ...]], ...]
    unresolved_member_ids: tuple[str, ...]
    unresolved_step_ids: tuple[str, ...]
    safe_unapplied_candidate_ids: tuple[str, ...]
    status: str
    # A read-only audit never infers that cleanup was applied. These fields are
    # populated only by an explicit cleanup owner after source change and
    # affected revalidation.
    applied_candidate_ids: tuple[str, ...] = ()
    application_evidence_fingerprint: str = ""
    review_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.reduction_universe_fingerprint != self.reduction_universe.fingerprint:
            raise ValueError(
                "self reduction universe fingerprint does not match its inventory"
            )
        if (
            self.candidate_evidence_neighborhood_catalog_fingerprint
            != self.candidate_evidence_neighborhood_catalog.fingerprint
        ):
            raise ValueError(
                "self reduction evidence neighborhood catalog fingerprint mismatch"
            )
        used_neighborhood_ids: set[str] = set()
        for candidate in self.candidates:
            contract = _normalized_candidate_observable_contract(candidate)
            neighborhood_id = contract["evidence_neighborhood_id"]
            neighborhood = self.candidate_evidence_neighborhood_catalog.resolve(
                neighborhood_id
            )
            if (
                contract["evidence_neighborhood_fingerprint"]
                != neighborhood.fingerprint
            ):
                raise ValueError(
                    "self reduction candidate evidence neighborhood fingerprint "
                    "does not match the review catalog"
                )
            used_neighborhood_ids.add(neighborhood_id)
        if used_neighborhood_ids != set(
            self.candidate_evidence_neighborhood_catalog.neighborhood_ids
        ):
            raise ValueError(
                "self reduction evidence neighborhood catalog contains an "
                "unreferenced or missing entry"
            )
        unresolved = tuple(
            sorted(
                row.member_id
                for row in self.reduction_universe.members
                if row.disposition == "unresolved"
            )
        )
        if tuple(self.unresolved_member_ids) != unresolved:
            raise ValueError(
                "self reduction unresolved member ids do not match the universe"
            )
        gap_counts = dict(self.necessity_gap_counts_by_kind)
        gap_examples = dict(self.necessity_gap_examples_by_kind)
        if (
            tuple(self.necessity_gap_counts_by_kind)
            != tuple(sorted(self.necessity_gap_counts_by_kind))
            or len(gap_counts) != len(self.necessity_gap_counts_by_kind)
            or tuple(self.necessity_gap_examples_by_kind)
            != tuple(sorted(self.necessity_gap_examples_by_kind))
            or set(gap_examples) != set(gap_counts)
            or any(count < 1 for count in gap_counts.values())
            or any(
                not member_ids
                or len(member_ids) > 8
                or tuple(member_ids) != tuple(sorted(set(member_ids)))
                or len(member_ids) > gap_counts[gap_id]
                or not set(member_ids) <= set(unresolved)
                for gap_id, member_ids in gap_examples.items()
            )
        ):
            raise ValueError(
                "self reduction necessity-gap diagnostics are not canonical"
            )
        unresolved_steps = tuple(
            sorted(
                row.step_id
                for row in self.reduction_report.step_assessments
                if row.action == STEP_ACTION_UNRESOLVED
            )
        )
        if tuple(self.unresolved_step_ids) != unresolved_steps:
            raise ValueError(
                "self reduction unresolved step ids do not match the step assessments"
            )
        expected_candidate_ids = {
            candidate.candidate_id for candidate in self.candidates
        }
        assessed_candidate_ids = {
            row.candidate_id
            for row in self.reduction_report.step_assessments
            if row.candidate_id
        }
        expected_step_decision_complete = bool(
            expected_candidate_ids == assessed_candidate_ids
            and len(self.reduction_report.step_assessments)
            == len(self.candidates)
            and not unresolved_steps
        )
        if self.step_decision_complete != expected_step_decision_complete:
            raise ValueError(
                "self reduction step decision completeness does not match the candidate assessments"
            )
        authorized_candidate_ids = tuple(
            sorted(self.reduction_report.ready_candidate_ids)
        )
        if self.action_authorized_candidate_ids != authorized_candidate_ids:
            raise ValueError(
                "self reduction action authorization does not match the "
                "current reduction report"
            )
        if self.safe_unapplied_candidate_ids != authorized_candidate_ids:
            raise ValueError(
                "self reduction safe-unapplied candidates do not match "
                "current action authorization"
            )
        candidate_ids = {candidate.candidate_id for candidate in self.candidates}
        if not set(self.applied_candidate_ids) <= candidate_ids:
            raise ValueError(
                "self reduction applied candidates must belong to the current candidate inventory"
            )
        if self.applied_candidate_ids and not self.application_evidence_fingerprint:
            raise ValueError(
                "self reduction applied candidates require application evidence"
            )
        if self.audit_complete and (
            not self.audit_accounted
            or not self.denominator_complete
            or not self.reduction_report.ok
        ):
            raise ValueError(
                "self reduction audit completion requires a complete, "
                "accounted, green review"
            )
        if self.cleanup_release_ready and (
            not self.audit_complete
            or not self.candidate_review_complete
            or not self.step_decision_complete
            or self.unresolved_member_ids
            or self.unresolved_step_ids
            or self.safe_unapplied_candidate_ids
        ):
            raise ValueError(
                "cleanup release readiness requires complete candidate and step decisions with zero unresolved or unapplied actions"
            )
        if (self.status == "pass") != (
            self.audit_complete and not self.safe_unapplied_candidate_ids
        ):
            raise ValueError(
                "self reduction pass status must represent a complete audit "
                "with no authorized-but-unapplied action"
            )
        object.__setattr__(
            self,
            "review_fingerprint",
            fingerprint_value(self.identity_payload()),
        )

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    @property
    def candidate_inventory_complete(self) -> bool:
        """Whether the independent candidate denominator is fully accounted for."""

        return bool(
            self.denominator_complete
            and self.candidate_inventory_independent
            and self.audit_accounted
        )

    @property
    def candidate_proof_complete(self) -> bool:
        """Whether every candidate has a complete decision, even if unapplied."""

        return bool(
            self.candidate_review_complete
            and self.step_decision_complete
            and not self.unresolved_member_ids
            and not self.unresolved_step_ids
        )

    @property
    def simplification_applied_and_verified(self) -> bool:
        """Whether a separately authorized cleanup was applied and revalidated."""

        return bool(
            self.applied_candidate_ids
            and self.application_evidence_fingerprint
            and self.cleanup_release_ready
            and not set(self.applied_candidate_ids).intersection(
                self.safe_unapplied_candidate_ids
            )
        )

    @property
    def schema_version(self) -> str:
        return SELF_ARCHITECTURE_REDUCTION_SCHEMA

    @property
    def claim_boundary(self) -> str:
        return (
            "This read-only review accounts for the independent complete self "
            "reduction universe before classifying structural candidates. "
            "Similarity and size are not behavior-equivalence proof, and this "
            "review edits no code. Audit accounting is separate from cleanup "
            "release readiness. Proofless candidates remain unresolved unless "
            "exact-current distinct behavior commitments independently justify "
            "a typed retain decision; unresolved steps block cleanup readiness "
            "without making an otherwise complete audit fail. Action authorization admits only "
            "an exact-current proven candidate to its required next route; it "
            "never authorizes automatic deletion."
        )

    @property
    def fingerprint(self) -> str:
        return self.review_fingerprint

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "self_blueprint_fingerprint": self.self_blueprint_fingerprint,
            "implementation_inventory_fingerprint": (
                self.implementation_inventory_fingerprint
            ),
            "behavior_report_fingerprint": self.behavior_report_fingerprint,
            "reduction_universe": self.reduction_universe.to_dict(),
            "reduction_universe_fingerprint": (
                self.reduction_universe_fingerprint
            ),
            "candidate_inventory_fingerprint": (
                self.candidate_inventory_fingerprint
            ),
            "candidate_evidence_neighborhood_catalog": (
                self.candidate_evidence_neighborhood_catalog.to_dict()
            ),
            "candidate_evidence_neighborhood_catalog_fingerprint": (
                self.candidate_evidence_neighborhood_catalog_fingerprint
            ),
            "proof_registry_fingerprint": self.proof_registry_fingerprint,
            "retain_registry_fingerprint": self.retain_registry_fingerprint,
            "retain_dispositions": [
                row.to_dict() for row in self.retain_dispositions
            ],
            "candidates": [row.to_dict() for row in self.candidates],
            "compatibility_classifications": [
                row.to_dict() for row in self.compatibility_classifications
            ],
            "reduction_report": self.reduction_report.to_dict(),
            "denominator_complete": self.denominator_complete,
            "candidate_review_complete": self.candidate_review_complete,
            "step_decision_complete": self.step_decision_complete,
            "candidate_inventory_independent": (
                self.candidate_inventory_independent
            ),
            "candidate_inventory_complete": self.candidate_inventory_complete,
            "candidate_proof_complete": self.candidate_proof_complete,
            "audit_accounted": self.audit_accounted,
            "audit_complete": self.audit_complete,
            "action_authorized_candidate_ids": list(
                self.action_authorized_candidate_ids
            ),
            "cleanup_release_ready": self.cleanup_release_ready,
            "simplification_applied_and_verified": (
                self.simplification_applied_and_verified
            ),
            "necessity_gap_counts_by_kind": dict(
                self.necessity_gap_counts_by_kind
            ),
            "necessity_gap_examples_by_kind": {
                gap_id: list(member_ids)
                for gap_id, member_ids in self.necessity_gap_examples_by_kind
            },
            "unresolved_member_ids": list(self.unresolved_member_ids),
            "unresolved_step_ids": list(self.unresolved_step_ids),
            "safe_unapplied_candidate_ids": list(
                self.safe_unapplied_candidate_ids
            ),
            "applied_candidate_ids": list(self.applied_candidate_ids),
            "application_evidence_fingerprint": (
                self.application_evidence_fingerprint
            ),
            "status": self.status,
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.identity_payload()
        return {
            **payload,
            "ok": self.ok,
            "review_fingerprint": self.review_fingerprint,
            "fingerprint": self.review_fingerprint,
        }


def _block_conflicting_candidate_actions(
    candidates: tuple[ArchitectureReductionCandidate, ...],
) -> tuple[ArchitectureReductionCandidate, ...]:
    """Block overlapping ready actions unless one unique action owns the member."""

    ready_by_member: dict[str, list[ArchitectureReductionCandidate]] = {}
    for candidate in candidates:
        if candidate.proof_status not in {
            PROOF_SAFE_BY_EQUIVALENCE,
            PROOF_SAFE_BY_PUBLIC_FACADE,
        }:
            continue
        for member_id in candidate.metadata.get("member_ids", ()):
            ready_by_member.setdefault(str(member_id), []).append(candidate)
    conflicting_candidate_ids: dict[str, set[str]] = {}
    for rows in ready_by_member.values():
        if len({row.target_action for row in rows}) < 2:
            continue
        conflict_ids = {row.candidate_id for row in rows}
        for candidate_id in conflict_ids:
            conflicting_candidate_ids.setdefault(candidate_id, set()).update(
                conflict_ids
            )
    if not conflicting_candidate_ids:
        return candidates
    target_action_by_candidate_id = {
        candidate.candidate_id: candidate.target_action for candidate in candidates
    }
    blocked_candidates: list[ArchitectureReductionCandidate] = []
    for candidate in candidates:
        conflict_ids = conflicting_candidate_ids.get(candidate.candidate_id)
        if not conflict_ids:
            blocked_candidates.append(candidate)
            continue
        metadata = dict(candidate.metadata)
        metadata["disposition"] = "unresolved"
        metadata["candidate_action_conflict_ids"] = tuple(sorted(conflict_ids))
        metadata["conflicting_target_actions"] = tuple(
            sorted(
                {
                    target_action_by_candidate_id[candidate_id]
                    for candidate_id in conflict_ids
                }
            )
        )
        metadata["missing_proof_obligations"] = tuple(
            sorted(
                {
                    *metadata.get("missing_proof_obligations", ()),
                    "unique_primary_candidate_action",
                }
            )
        )
        blocked_candidates.append(
            replace(
                candidate,
                candidate_type=CANDIDATE_MANUAL_REVIEW,
                target_action=TARGET_ACTION_MANUAL_REVIEW,
                proof_status=PROOF_RISKY_KEEP,
                required_next_route=ROUTE_STRUCTURE_MESH,
                rationale=(
                    "Multiple independently proved contraction actions claim the "
                    "same code member, and no unique primary action authority exists."
                ),
                metadata=metadata,
                business_intent_id="",
                behavior_commitment_id="",
                primary_path_id="",
                owner_code_contract_id="",
                delegates_to_code_contract_id="",
                delegates_to_primary_path_id="",
                delegation_evidence_id="",
                delegation_evidence_current=False,
                delegation_only=False,
                independent_business_authority=False,
            )
        )
    return tuple(blocked_candidates)


def _self_reduction_candidates(
    bundle: FlowGuardSelfBlueprintBundle,
    *,
    root: str | Path | None = None,
    reduction_universe: SelfReductionUniverse,
    proof_records: tuple[_VerifiedSelfReductionProof, ...] = (),
) -> tuple[
    tuple[ArchitectureReductionCandidate, ...],
    str,
    tuple[CompatibilitySurfaceClassification, ...],
    SelfReductionEvidenceNeighborhoodCatalog,
]:
    surfaces = tuple(bundle.inventory.surfaces)
    implementation_inventory_fingerprint = bundle.inventory.inventory_fingerprint
    test_inventory_fingerprint = bundle.test_inventory.inventory_fingerprint
    behavior_report_fingerprint = bundle.behavior_report.fingerprint
    manifest_fingerprint = bundle.manifest.fingerprint
    surface_by_id = {row.surface_id: row for row in surfaces}
    required_surface_ids = set(bundle.inventory.required_surface_ids)
    call_index = _reverse_call_alias_index(surfaces, root=root)
    signal_kinds_by_surface: dict[str, frozenset[str]] = {}
    for row in reduction_universe.members:
        member_id = str(row.member_id)
        signal_kinds = frozenset(str(value) for value in row.signal_kinds)
        if member_id in required_surface_ids and signal_kinds:
            signal_kinds_by_surface[member_id] = signal_kinds
    branch_signal_surface_ids = {
        surface_id
        for surface_id, signal_kinds in signal_kinds_by_surface.items()
        if "branch_signal" in signal_kinds
    }

    proof_by_candidate: dict[
        tuple[str, tuple[str, ...]], SelfReductionProofRecord
    ] = {}
    for proof in proof_records:
        proof_key = (proof.candidate_signal, proof.member_ids)
        if proof_key in proof_by_candidate:
            raise ValueError(
                "self reduction proof registry contains duplicate candidate coverage"
            )
        proof_by_candidate[proof_key] = proof

    candidate_payloads: list[dict[str, Any]] = []
    branch_or_helper_group_index: dict[
        tuple[str, tuple[str, ...]], int
    ] = {}

    behavior_contracts = tuple(getattr(bundle.behavior_report, "contracts", ()))
    supporting_relations = tuple(
        getattr(bundle.behavior_report, "supporting_relations", ())
    )
    coverage_edges = tuple(getattr(bundle.behavior_report, "coverage_edges", ()))
    coverage_execution: dict[str, Any] = {}
    for row in getattr(
        bundle.behavior_report,
        "coverage_execution_evidence",
        (),
    ):
        coverage_id = str(getattr(row, "coverage_id", ""))
        if coverage_id:
            coverage_execution[coverage_id] = row

    behavior_surface_ids: set[str] = set()
    behavior_ids_by_surface: dict[str, set[str]] = {}
    model_ids_by_surface: dict[str, set[str]] = {}
    owner_ids_by_surface: dict[str, set[str]] = {}
    for row in behavior_contracts:
        surface_id = str(getattr(row, "implementation_surface_id", ""))
        behavior_surface_ids.add(surface_id)
        behavior_id = str(getattr(row, "behavior_block_id", ""))
        model_id = str(getattr(row, "model_element_id", ""))
        owner_id = str(getattr(row, "owner_id", ""))
        if behavior_id:
            behavior_ids_by_surface.setdefault(surface_id, set()).add(
                behavior_id
            )
        if model_id:
            model_ids_by_surface.setdefault(surface_id, set()).add(model_id)
        if owner_id:
            owner_ids_by_surface.setdefault(surface_id, set()).add(owner_id)

    for row in supporting_relations:
        surface_id = str(getattr(row, "supporting_surface_id", ""))
        behavior_id = str(getattr(row, "behavior_block_id", ""))
        if behavior_id:
            behavior_ids_by_surface.setdefault(surface_id, set()).add(
                behavior_id
            )

    coverage_ordinals_by_behavior: dict[str, list[int]] = {}
    coverage_ordinals_by_surface_behavior: dict[
        tuple[str, str], list[int]
    ] = {}
    coverage_bucket_keys_by_surface: dict[
        str, set[tuple[str, str]]
    ] = {}
    coverage_metadata: list[tuple[str, str, tuple[str, ...], str]] = []
    for ordinal, row in enumerate(coverage_edges):
        surface_id = str(getattr(row, "implementation_surface_id", ""))
        behavior_id = str(getattr(row, "behavior_block_id", ""))
        coverage_id = str(getattr(row, "coverage_id", ""))
        test_id = str(getattr(row, "test_node_id", ""))
        dimensions = tuple(
            str(dimension)
            for dimension in getattr(row, "covered_dimensions", ())
            if str(dimension)
        )
        current_receipt_id = ""
        execution = coverage_execution.get(coverage_id)
        if (
            execution is not None
            and str(getattr(execution, "disposition", "")) == "pass"
        ):
            current_receipt_id = str(getattr(execution, "receipt_id", ""))
        coverage_ordinals_by_behavior.setdefault(behavior_id, []).append(
            ordinal
        )
        bucket_key = (surface_id, behavior_id)
        coverage_ordinals_by_surface_behavior.setdefault(
            bucket_key,
            [],
        ).append(ordinal)
        coverage_bucket_keys_by_surface.setdefault(surface_id, set()).add(
            bucket_key
        )
        coverage_metadata.append(
            (test_id, coverage_id, dimensions, current_receipt_id)
        )

    neighborhood_by_recipe: dict[
        tuple[tuple[str, ...], tuple[tuple[str, str], ...]],
        SelfReductionEvidenceNeighborhood,
    ] = {}
    neighborhood_by_id: dict[str, SelfReductionEvidenceNeighborhood] = {}

    def evidence_neighborhood(
        member_ids: tuple[str, ...],
        behavior_ids: tuple[str, ...],
    ) -> SelfReductionEvidenceNeighborhood:
        behavior_id_set = set(behavior_ids)
        extra_bucket_keys = tuple(
            sorted(
                {
                    bucket_key
                    for member_id in member_ids
                    for bucket_key in coverage_bucket_keys_by_surface.get(
                        member_id,
                        (),
                    )
                    if bucket_key[1] not in behavior_id_set
                }
            )
        )
        recipe = (behavior_ids, extra_bucket_keys)
        cached = neighborhood_by_recipe.get(recipe)
        if cached is not None:
            return cached
        matching_ordinals: set[int] = set()
        for behavior_id in behavior_ids:
            matching_ordinals.update(
                coverage_ordinals_by_behavior.get(behavior_id, ())
            )
        for bucket_key in extra_bucket_keys:
            matching_ordinals.update(
                coverage_ordinals_by_surface_behavior.get(bucket_key, ())
            )
        matching_rows = tuple(
            coverage_metadata[ordinal]
            for ordinal in sorted(matching_ordinals)
        )
        neighborhood = SelfReductionEvidenceNeighborhood(
            test_node_ids=tuple(
                test_id
                for test_id, _, _, _ in matching_rows
                if test_id
            ),
            coverage_ids=tuple(
                coverage_id
                for _, coverage_id, _, _ in matching_rows
                if coverage_id
            ),
            covered_dimensions=tuple(
                dimension
                for _, _, dimensions, _ in matching_rows
                for dimension in dimensions
            ),
            current_test_receipt_ids=tuple(
                receipt_id
                for _, _, _, receipt_id in matching_rows
                if receipt_id
            ),
        )
        existing = neighborhood_by_id.get(neighborhood.neighborhood_id)
        if existing is not None and existing != neighborhood:
            raise ValueError(
                "self reduction evidence neighborhood identity collision"
            )
        neighborhood = existing or neighborhood
        neighborhood_by_id[neighborhood.neighborhood_id] = neighborhood
        neighborhood_by_recipe[recipe] = neighborhood
        return neighborhood

    def proof_metadata(
        exact_members: tuple[Any, ...],
        *,
        signal: str,
        caller_ids: tuple[str, ...],
        caller_resolution_gap_ids: tuple[str, ...],
        public_entrypoint_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        """Describe the proof still needed without upgrading a signal to proof."""

        member_ids = {str(row.surface_id) for row in exact_members}
        behavior_id_values: set[str] = set()
        model_id_values: set[str] = set()
        owner_id_values: set[str] = set()
        for member_id in member_ids:
            behavior_id_values.update(
                behavior_ids_by_surface.get(member_id, ())
            )
            model_id_values.update(model_ids_by_surface.get(member_id, ()))
            owner_id_values.update(owner_ids_by_surface.get(member_id, ()))
        behavior_ids = tuple(sorted(behavior_id_values))
        model_ids = tuple(sorted(model_id_values))
        owner_ids = tuple(sorted(owner_id_values))
        neighborhood = evidence_neighborhood(
            tuple(sorted(member_ids)),
            behavior_ids,
        )
        state_reads = tuple(
            sorted(
                {
                    str(value)
                    for row in exact_members
                    for value in getattr(row, "state_reads", ())
                    if str(value)
                }
            )
        )
        state_writes = tuple(
            sorted(
                {
                    str(value)
                    for row in exact_members
                    for value in getattr(row, "state_writes", ())
                    if str(value)
                }
            )
        )
        side_effects = tuple(
            sorted(
                {
                    str(value)
                    for row in exact_members
                    for value in getattr(row, "side_effect_candidates", ())
                    if str(value)
                }
            )
        )
        raised_errors = tuple(
            sorted(
                {
                    str(value)
                    for row in exact_members
                    for value in getattr(row, "raised_errors", ())
                    if str(value)
                }
            )
        )
        required_route_ids = {
            ROUTE_DEVELOPMENT_PROCESS_FLOW,
            ROUTE_MODEL_TEST_ALIGNMENT,
        }
        if public_entrypoint_ids or signal in {
            "oversized_module",
            "duplicate_route",
            "adapter_layer",
            "wrapper_or_facade",
            "helper_path",
            "fallback_alias_compatibility_path",
            "repeated_builder",
        }:
            required_route_ids.add(ROUTE_STRUCTURE_MESH)
        missing_proof_obligations = [
            "current_observable_equivalence",
            "caller_consumer_parity",
        ]
        if state_reads or state_writes:
            missing_proof_obligations.append("state_parity")
        if side_effects:
            missing_proof_obligations.append("side_effect_parity")
        if raised_errors:
            missing_proof_obligations.append("error_parity")
        if public_entrypoint_ids:
            missing_proof_obligations.extend(
                (
                    "public_facade_delegation",
                    "exact_public_surface_ledger_anchor",
                    "exact_bcl_owner_code_contract_binding",
                )
            )
        if behavior_ids and not neighborhood.test_node_ids:
            missing_proof_obligations.append("exact_behavior_test_binding")
        if caller_resolution_gap_ids:
            missing_proof_obligations.append("canonical_caller_resolution")
        observable_contract = {
            "schema_version": SELF_REDUCTION_OBSERVABLE_CONTRACT_SCHEMA,
            "caller_consumer_ids": caller_ids,
            "behavior_block_ids": behavior_ids,
            "model_element_ids": model_ids,
            "owner_ids": owner_ids,
            "state_reads": state_reads,
            "state_writes": state_writes,
            "side_effect_ids": side_effects,
            "raised_error_ids": raised_errors,
            "evidence_neighborhood_id": neighborhood.neighborhood_id,
            "evidence_neighborhood_fingerprint": neighborhood.fingerprint,
        }
        return {
            "observable_contract": observable_contract,
            "observable_contract_fingerprint": fingerprint_value(
                observable_contract
            ),
            "missing_proof_obligations": tuple(missing_proof_obligations),
            "caller_resolution_gap_ids": caller_resolution_gap_ids,
            "required_route_ids": tuple(sorted(required_route_ids)),
        }

    def append_group(
        signal: str,
        members: list[Any] | tuple[Any, ...],
        *,
        group_key: str,
        disposition: str = "unresolved",
        extra: dict[str, Any] | None = None,
    ) -> None:
        exact_members = tuple(sorted(members, key=lambda row: row.surface_id))
        if not exact_members:
            return
        caller_ids = _indexed_caller_ids(
            exact_members,
            call_index=call_index,
        )
        caller_resolution_gap_ids = _indexed_caller_gap_ids(
            exact_members,
            call_index=call_index,
        )
        public_entrypoint_ids = tuple(
            row.surface_id
            for row in exact_members
            if "entrypoint" in getattr(row, "roles", ())
            or row.surface_kind == "entrypoint"
        )
        signal_kind_by_candidate = {
            "oversized_module": "oversized_boundary_signal",
            "repeated_behavior_shape": "repeated_shape_signal",
            "duplicate_route": "command_route_signal",
            "duplicate_branch": "branch_signal",
            "adapter_layer": "adapter_signal",
            "wrapper_or_facade": "wrapper_facade_signal",
            "helper_path": "helper_signal",
            "validation_path": "validation_signal",
            "fallback_alias_compatibility_path": "maintenance_name_signal",
            "repeated_builder": "builder_signal",
            "serialization_path": "serialization_signal",
            "unreferenced_helper": "helper_signal",
        }
        required_signal_kind = signal_kind_by_candidate[signal]
        payload = {
            "signal": signal,
            "group_key": group_key,
            "disposition": disposition,
            "paths": tuple(sorted({row.path for row in exact_members})),
            "member_ids": tuple(row.surface_id for row in exact_members),
            "source_signal_ids": tuple(
                sorted(
                    {
                        str(row.surface_id)
                        for row in exact_members
                        if required_signal_kind
                        in signal_kinds_by_surface.get(
                            str(row.surface_id), frozenset()
                        )
                    }
                )
            ),
            "caller_ids": caller_ids,
            "caller_resolution_gap_ids": caller_resolution_gap_ids,
            "public_entrypoint_ids": public_entrypoint_ids,
            **proof_metadata(
                exact_members,
                signal=signal,
                caller_ids=caller_ids,
                caller_resolution_gap_ids=caller_resolution_gap_ids,
                public_entrypoint_ids=public_entrypoint_ids,
            ),
        }
        if extra:
            payload.update(extra)
        payload_bytes = len(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        operation_count = sum(
            max(1, len(tuple(getattr(row, "calls", ()))))
            for row in exact_members
        )
        cost_seed = {
            "subject_revision": bundle.inventory.boundary.subject_revision,
            "inventory_fingerprint": implementation_inventory_fingerprint,
            "signal": signal,
            "group_key": group_key,
            "member_ids": payload["member_ids"],
            "operation_count": operation_count,
            "payload_bytes": payload_bytes,
            "invocation_count": max(1, len(caller_ids)),
        }
        cost = ArchitectureReductionStepCost(
            measurement_id=(
                "self-step-cost:"
                + fingerprint_value(cost_seed).split(":", 1)[1]
            ),
            subject_revision=bundle.inventory.boundary.subject_revision,
            source_ref=(
                "self-blueprint:" + implementation_inventory_fingerprint
            ),
            measurement_mode="static_inventory_projection",
            operation_count=operation_count,
            payload_bytes=payload_bytes,
            estimated_token_count=(payload_bytes + 3) // 4,
            invocation_count=max(1, len(caller_ids)),
            current=True,
            rationale=(
                "Static call-edge units and exact canonical candidate-projection "
                "bytes prioritize review only; they do not prove contraction safe."
            ),
        )
        payload["step_cost_evidence"] = cost.to_dict()
        group_identity = (
            group_key,
            tuple(row.surface_id for row in exact_members),
        )
        existing_index = branch_or_helper_group_index.get(group_identity)
        if existing_index is not None and signal == "helper_path":
            existing_signal = str(
                candidate_payloads[existing_index].get("signal", "")
            )
            if existing_signal == "duplicate_branch":
                candidate_payloads[existing_index] = payload
                return
        if signal in {"duplicate_branch", "helper_path"}:
            branch_or_helper_group_index.setdefault(
                group_identity,
                len(candidate_payloads),
            )
        candidate_payloads.append(payload)
    # Oversized boundaries remain explicit StructureMesh triggers in the
    # independent universe.  Size alone supplies neither a model-derived child
    # structure nor a concrete contraction action, so it must not manufacture
    # one ArchitectureReduction candidate for every large module.

    by_shape: dict[str, list[Any]] = {}
    for surface_id in behavior_surface_ids:
        surface = surface_by_id[surface_id]
        by_shape.setdefault(surface.structure_fingerprint, []).append(surface)
    for structure_fingerprint, members in sorted(by_shape.items()):
        paths = {row.path for row in members}
        if len(members) < 3 or len(paths) < 2:
            continue
        append_group(
            "repeated_behavior_shape",
            members,
            group_key=structure_fingerprint,
            extra={"structure_fingerprint": structure_fingerprint},
        )

    required_surfaces = tuple(
        row
        for row in surfaces
        if row.surface_id in required_surface_ids
        and row.surface_kind not in {"module", "class"}
    )

    def symbol_has_marker(surface: Any, markers: tuple[str, ...]) -> bool:
        name = (
            getattr(surface, "symbol", surface.surface_id)
            .rsplit(".", 1)[-1]
            .lower()
        )
        return any(
            name == marker
            or name.startswith(marker + "_")
            or name.endswith("_" + marker)
            or (marker in {"to_dict", "from_dict"} and marker in name)
            for marker in markers
        )

    def grouped_candidates(
        signal: str,
        selected: tuple[Any, ...],
        key_builder: Any,
        *,
        public_is_retain: bool = False,
    ) -> None:
        groups: dict[str, list[Any]] = {}
        for surface in selected:
            key = str(key_builder(surface))
            if key:
                groups.setdefault(key, []).append(surface)
        for key, members in sorted(groups.items()):
            exact_members = tuple(
                sorted(members, key=lambda row: row.surface_id)
            )
            if len(exact_members) < 2:
                continue
            batch_count = (
                len(exact_members)
                + SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
                - 1
            ) // SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
            base_batch_size, larger_batch_count = divmod(
                len(exact_members),
                batch_count,
            )
            offset = 0
            for batch_index in range(batch_count):
                batch_size = base_batch_size + (
                    1 if batch_index < larger_batch_count else 0
                )
                batch = exact_members[offset : offset + batch_size]
                offset += batch_size
                disposition = (
                    "retain"
                    if public_is_retain
                    and any(
                        "entrypoint" in getattr(row, "roles", ())
                        or row.surface_kind == "entrypoint"
                        for row in batch
                    )
                    else "unresolved"
                )
                append_group(
                    signal,
                    batch,
                    group_key=(
                        key
                        if batch_count == 1
                        else f"{key}#batch:{batch_index + 1:04d}"
                    ),
                    disposition=disposition,
                    extra={
                        "relation_group_member_count": len(exact_members),
                        "batch_index": batch_index + 1,
                        "batch_count": batch_count,
                        "batch_member_limit": (
                            SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
                        ),
                    },
                )

    def exact_call_structure_key(surface: Any) -> str:
        return fingerprint_value(
            {
                "schema_version": (
                    "flowguard.self_reduction_exact_relation_key.v1"
                ),
                "surface_kind": str(surface.surface_kind),
                "calls": tuple(
                    str(value)
                    for value in getattr(surface, "calls", ())
                    if str(value)
                ),
                "structure_fingerprint": str(
                    surface.structure_fingerprint
                ),
            }
        )

    entrypoints = tuple(
        row
        for row in required_surfaces
        if "entrypoint" in getattr(row, "roles", ())
        or row.surface_kind == "entrypoint"
    )
    grouped_candidates(
        "duplicate_route",
        entrypoints,
        exact_call_structure_key,
        public_is_retain=True,
    )
    grouped_candidates(
        "duplicate_branch",
        tuple(
            row
            for row in required_surfaces
            if str(row.surface_id) in branch_signal_surface_ids
        ),
        exact_call_structure_key,
    )
    grouped_candidates(
        "adapter_layer",
        tuple(
            row
            for row in required_surfaces
            if any(
                token
                in (row.path + "#" + getattr(row, "symbol", row.surface_id)).lower()
                for token in ("adapter", "provider", "discover")
            )
        ),
        exact_call_structure_key,
    )
    grouped_candidates(
        "wrapper_or_facade",
        tuple(
            row
            for row in required_surfaces
            if len(getattr(row, "calls", ())) <= 1
            and not getattr(row, "symbol", row.surface_id)
            .rsplit(".", 1)[-1]
            .startswith("_")
        ),
        exact_call_structure_key,
        public_is_retain=True,
    )
    grouped_candidates(
        "helper_path",
        tuple(
            row
            for row in required_surfaces
            if getattr(row, "symbol", row.surface_id)
            .rsplit(".", 1)[-1]
            .startswith("_")
            and _indexed_caller_ids(
                (row,),
                call_index=call_index,
            )
        ),
        exact_call_structure_key,
    )
    grouped_candidates(
        "validation_path",
        tuple(
            row
            for row in required_surfaces
            if any(
                token
                in getattr(row, "symbol", row.surface_id)
                .rsplit(".", 1)[-1]
                .lower()
                for token in ("check", "review", "validate", "verify", "audit")
            )
        ),
        exact_call_structure_key,
    )

    maintenance_tokens = ("fallback", "alias", "compat", "legacy", "deprecated")
    maintenance_surfaces = tuple(
        row
        for row in required_surfaces
        if any(
            token
            in (row.path + "#" + getattr(row, "symbol", row.surface_id)).lower()
            for token in maintenance_tokens
        )
    )
    # A maintenance-looking name is a review signal, not a contraction
    # relation.  Materialize a candidate only when two or more current
    # surfaces share the same exact call and structure relation.
    # Every named surface is still classified below, including isolated rows.
    grouped_candidates(
        "fallback_alias_compatibility_path",
        maintenance_surfaces,
        exact_call_structure_key,
    )

    grouped_candidates(
        "repeated_builder",
        tuple(
            row
            for row in required_surfaces
            if symbol_has_marker(
                row,
                ("build", "compile", "construct", "create", "derive"),
            )
        ),
        exact_call_structure_key,
    )
    grouped_candidates(
        "serialization_path",
        tuple(
            row
            for row in required_surfaces
            if symbol_has_marker(
                row,
                (
                    "serialize",
                    "deserialize",
                    "to_dict",
                    "from_dict",
                    "dump",
                    "load",
                ),
            )
        ),
        exact_call_structure_key,
    )
    dead_helpers_by_path: dict[str, list[Any]] = {}
    for row in required_surfaces:
        symbol = getattr(row, "symbol", row.surface_id).rsplit(".", 1)[-1]
        if not symbol.startswith("_"):
            continue
        if _indexed_caller_ids(
            (row,),
            call_index=call_index,
        ):
            continue
        if _indexed_caller_gap_ids((row,), call_index=call_index):
            continue
        dead_helpers_by_path.setdefault(row.path, []).append(row)
    for path, members in sorted(dead_helpers_by_path.items()):
        exact_members = tuple(
            sorted(members, key=lambda row: row.surface_id)
        )
        batch_count = (
            len(exact_members)
            + SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
            - 1
        ) // SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
        for batch_index in range(batch_count):
            start = (
                batch_index
                * SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
            )
            batch = exact_members[
                start : start
                + SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
            ]
            append_group(
                "unreferenced_helper",
                batch,
                group_key=f"{path}#batch:{batch_index + 1:04d}",
                extra={
                    "batch_index": batch_index + 1,
                    "batch_count": batch_count,
                    "batch_member_limit": (
                        SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT
                    ),
                },
            )

    evidence_neighborhood_catalog = SelfReductionEvidenceNeighborhoodCatalog(
        tuple(neighborhood_by_id.values())
    )
    inventory_payload = {
        "schema_version": SELF_REDUCTION_CANDIDATE_INVENTORY_SCHEMA,
        "implementation_inventory_fingerprint": implementation_inventory_fingerprint,
        "behavior_report_fingerprint": behavior_report_fingerprint,
        "signal_policy": {
            "oversized_module": (
                "StructureMesh trigger only until a model-derived target child "
                "structure identifies one concrete contraction action"
            ),
            "repeated_behavior_shape": {
                "member_count_gte": 3,
                "distinct_path_count_gte": 2,
            },
            "duplicate_route": "same current call/structure signature across entrypoints",
            "duplicate_branch": "same current structure among surfaces with concrete branch syntax",
            "adapter_layer": "same adapter/provider/discovery delegation signature",
            "wrapper_or_facade": "same zero/one-call public delegation signature",
            "helper_path": "same private helper delegation signature",
            "validation_path": "same validation/review/check delegation signature",
            "fallback_alias_compatibility_path": (
                "maintenance-name signal requiring direct-current authority review"
            ),
            "repeated_builder": "same builder delegation signature across files",
            "serialization_path": "same serialization delegation signature across files",
            "unreferenced_helper": (
                "no statically observed caller; exact members are split into "
                "deterministic finite batches of at most "
                f"{SELF_REDUCTION_CANDIDATE_MEMBER_LIMIT} while "
                "dynamic use remains an unresolved risk"
            ),
        },
        "candidate_payloads": candidate_payloads,
        "candidate_evidence_neighborhood_catalog": (
            evidence_neighborhood_catalog.to_dict()
        ),
        "candidate_evidence_neighborhood_catalog_fingerprint": (
            evidence_neighborhood_catalog.fingerprint
        ),
    }
    inventory_fingerprint = fingerprint_value(inventory_payload)
    candidates: list[ArchitectureReductionCandidate] = []
    maintenance_candidate_by_surface: dict[str, str] = {}
    for index, payload in enumerate(candidate_payloads, 1):
        signal = str(payload["signal"])
        node_id = str(payload["member_ids"][0])
        member_ids = tuple(sorted(str(value) for value in payload["member_ids"]))
        proof = proof_by_candidate.get((signal, member_ids))
        observable_contract_fingerprint = str(
            payload.get("observable_contract_fingerprint", "")
        )
        if not observable_contract_fingerprint:
            raise ValueError(
                "self reduction candidate lacks its exact observable contract "
                "fingerprint"
            )
        proof_ready = bool(
            proof is not None
            and proof.complete
            and proof.subject_revision
            == bundle.inventory.boundary.subject_revision
            and proof.inventory_fingerprint
            == implementation_inventory_fingerprint
            and proof.test_inventory_fingerprint
            == test_inventory_fingerprint
            and proof.observable_contract_fingerprint
            == observable_contract_fingerprint
        )
        proof_status = proof.proof_status if proof_ready and proof else PROOF_RISKY_KEEP
        if proof_status == PROOF_SAFE_BY_PUBLIC_FACADE:
            candidate_type = CANDIDATE_KEEP_PUBLIC_FACADE
            target_action = TARGET_ACTION_KEEP_FACADE
        elif proof_status == PROOF_SAFE_BY_EQUIVALENCE:
            if signal == "adapter_layer":
                candidate_type = CANDIDATE_COLLAPSE_ADAPTER
                target_action = TARGET_ACTION_COLLAPSE
            elif signal == "duplicate_branch":
                candidate_type = CANDIDATE_REMOVE_BRANCH
                target_action = TARGET_ACTION_REMOVE
            elif signal == "validation_path":
                candidate_type = CANDIDATE_REMOVE_DUPLICATE_VALIDATION
                target_action = TARGET_ACTION_REMOVE
            elif signal in {"oversized_module", "serialization_path"}:
                candidate_type = CANDIDATE_MERGE_MODULES
                target_action = TARGET_ACTION_MERGE
            else:
                candidate_type = CANDIDATE_MERGE_HANDLERS
                target_action = TARGET_ACTION_MERGE
        else:
            candidate_type = CANDIDATE_MANUAL_REVIEW
            target_action = TARGET_ACTION_MANUAL_REVIEW
        next_route = (
            ROUTE_STRUCTURE_MESH
            if payload.get("public_entrypoint_ids")
            or signal
            in {
                "oversized_module",
                "duplicate_route",
                "adapter_layer",
                "wrapper_or_facade",
                "helper_path",
                "fallback_alias_compatibility_path",
                "repeated_builder",
            }
            else ROUTE_MODEL_TEST_ALIGNMENT
        )
        observable_contract = dict(payload.get("observable_contract", {}))
        affected_state = tuple(
            sorted(
                {
                    *observable_contract.get("state_reads", ()),
                    *observable_contract.get("state_writes", ()),
                }
            )
        )
        affected_side_effects = tuple(
            observable_contract.get("side_effect_ids", ())
        )
        candidate_id = f"self-reduction:{signal}:{index:04d}"
        if signal == "fallback_alias_compatibility_path":
            for maintenance_member_id in member_ids:
                existing_candidate_id = maintenance_candidate_by_surface.get(
                    maintenance_member_id
                )
                if (
                    existing_candidate_id
                    and existing_candidate_id != candidate_id
                ):
                    raise ValueError(
                        "one maintenance surface belongs to multiple current "
                        "contraction relations"
                    )
                maintenance_candidate_by_surface[
                    maintenance_member_id
                ] = candidate_id
        candidate_metadata = dict(payload)
        candidate_metadata["disposition"] = (
            "contract" if proof_ready else "unresolved"
        )
        if proof_ready and proof is not None:
            candidate_metadata["proof_record_id"] = proof.proof_id
            candidate_metadata["proof_record_fingerprint"] = proof.fingerprint
            candidate_metadata["missing_proof_obligations"] = ()
        candidates.append(
            ArchitectureReductionCandidate(
                candidate_id=candidate_id,
                candidate_type=candidate_type,
                code_node_id=node_id,
                source_model_element=(
                    "self-blueprint:" + manifest_fingerprint
                ),
                target_action=target_action,
                proof_status=proof_status,
                required_next_route=next_route,
                rationale=(
                    "An independent current proof closes the exact observable "
                    "contract and parity obligations for this candidate."
                    if proof_ready
                    else "The independent inventory found a structural signal, "
                    "but current external proof does not close the exact observable "
                    "contract, so the path remains a risky keep."
                ),
                evidence_refs=(
                    manifest_fingerprint,
                    behavior_report_fingerprint,
                    inventory_fingerprint,
                    *(proof.evidence_refs if proof_ready and proof else ()),
                    *((proof.fingerprint,) if proof_ready and proof else ()),
                ),
                inventory_revision=inventory_fingerprint,
                metadata=candidate_metadata,
                affected_public_entrypoints=tuple(
                    payload.get("public_entrypoint_ids", ())
                ),
                affected_state=affected_state,
                affected_side_effects=affected_side_effects,
                business_intent_id=(
                    proof.business_intent_id if proof_ready and proof else ""
                ),
                behavior_commitment_id=(
                    proof.behavior_commitment_id if proof_ready and proof else ""
                ),
                primary_path_id=(
                    proof.primary_path_id if proof_ready and proof else ""
                ),
                owner_code_contract_id=(
                    proof.owner_code_contract_id if proof_ready and proof else ""
                ),
                delegates_to_code_contract_id=(
                    proof.delegates_to_code_contract_id
                    if proof_ready and proof
                    else ""
                ),
                delegates_to_primary_path_id=(
                    proof.delegates_to_primary_path_id
                    if proof_ready and proof
                    else ""
                ),
                delegation_evidence_id=(
                    proof.public_facade_delegation_evidence_id
                    if proof_ready and proof
                    else ""
                ),
                delegation_evidence_current=bool(proof_ready and proof),
                delegation_only=(
                    proof.delegation_only if proof_ready and proof else False
                ),
                independent_business_authority=(
                    proof.independent_business_authority
                    if proof_ready and proof
                    else False
                ),
            )
        )
    candidates = list(_block_conflicting_candidate_actions(tuple(candidates)))
    candidate_by_id = {row.candidate_id: row for row in candidates}
    compatibility_classifications = tuple(
        CompatibilitySurfaceClassification(
            surface_id=f"maintenance-signal:{surface.surface_id}",
            classification=(
                COMPATIBILITY_SURFACE_PRUNE_CANDIDATE
                if (
                    (candidate_id := maintenance_candidate_by_surface.get(
                        str(surface.surface_id), ""
                    ))
                    and candidate_by_id[candidate_id].proof_status
                    == PROOF_SAFE_BY_EQUIVALENCE
                )
                else COMPATIBILITY_SURFACE_CURRENT_CONTRACT
            ),
            recommended_action=(
                COMPATIBILITY_ACTION_PRUNE
                if candidate_id
                and candidate_by_id[candidate_id].proof_status
                == PROOF_SAFE_BY_EQUIVALENCE
                else COMPATIBILITY_ACTION_KEEP
            ),
            rationale=(
                "The exact executable surface is classified separately. Its name "
                "alone does not make it a legacy path; it remains a current contract "
                "unless independent equivalence proof authorizes pruning."
            ),
            code_node_ids=(str(surface.surface_id),),
            public_entrypoints=(
                (str(surface.surface_id),)
                if "entrypoint" in getattr(surface, "roles", ())
                or getattr(surface, "surface_kind", "") == "entrypoint"
                else ()
            ),
            runtime_authority=bool(
                "entrypoint" in getattr(surface, "roles", ())
                or "behavior" in getattr(surface, "roles", ())
                or getattr(surface, "surface_kind", "") == "entrypoint"
            ),
            candidate_ids=(
                (maintenance_candidate_by_surface[str(surface.surface_id)],)
                if str(surface.surface_id) in maintenance_candidate_by_surface
                else ()
            ),
            evidence_refs=(str(getattr(surface, "structure_fingerprint", "")),),
            missing_evidence=(
                ()
                if candidate_id
                and candidate_by_id[candidate_id].proof_status
                == PROOF_SAFE_BY_EQUIVALENCE
                else (
                    "current_observable_equivalence",
                    "external_consumer_contract",
                )
            ),
        )
        for surface in maintenance_surfaces
    )
    return (
        tuple(candidates),
        inventory_fingerprint,
        compatibility_classifications,
        evidence_neighborhood_catalog,
    )


def _self_step_assessments(
    candidates: tuple[ArchitectureReductionCandidate, ...],
    retain_dispositions: tuple[SelfReductionRetainDisposition, ...] = (),
) -> tuple[ArchitectureReductionStepAssessment, ...]:
    """Project existing self-candidates into retained-route step decisions.

    The candidate inventory remains the one discovery authority.  This is a
    bounded decision projection over that inventory, not a second scan.
    """

    step_kind_by_signal = {
        "oversized_module": STEP_KIND_MODULE_BOUNDARY,
        "repeated_behavior_shape": STEP_KIND_OTHER,
        "duplicate_route": STEP_KIND_ROUTE_DISPATCH,
        "duplicate_branch": STEP_KIND_BRANCH,
        "adapter_layer": STEP_KIND_ADAPTER,
        "wrapper_or_facade": STEP_KIND_ADAPTER,
        "helper_path": STEP_KIND_HELPER,
        "validation_path": STEP_KIND_VALIDATION,
        "fallback_alias_compatibility_path": STEP_KIND_ROUTE_DISPATCH,
        "repeated_builder": STEP_KIND_BUILDER,
        "serialization_path": STEP_KIND_SERIALIZATION,
        "unreferenced_helper": STEP_KIND_HELPER,
    }
    candidate_ids = {candidate.candidate_id for candidate in candidates}
    retain_by_candidate_id: dict[str, SelfReductionRetainDisposition] = {}
    current_necessity_by_member_id: dict[
        str, SelfReductionRetainDisposition
    ] = {}
    for disposition in retain_dispositions:
        for candidate_id in disposition.candidate_ids:
            if candidate_id not in candidate_ids:
                raise ValueError(
                    "candidate-level retain disposition references an unknown candidate"
                )
            if candidate_id in retain_by_candidate_id:
                raise ValueError(
                    "one self-reduction candidate has multiple retain decisions"
                )
            retain_by_candidate_id[candidate_id] = disposition
        if disposition.basis == "current_necessity_witness":
            for member_id in disposition.member_ids:
                if member_id in current_necessity_by_member_id:
                    raise ValueError(
                        "one self-reduction member has multiple current-necessity decisions"
                    )
                current_necessity_by_member_id[member_id] = disposition

    rows: list[ArchitectureReductionStepAssessment] = []
    for candidate in candidates:
        metadata = dict(candidate.metadata)
        signal = str(metadata.get("signal", ""))
        member_ids = tuple(
            sorted(
                str(value)
                for value in metadata.get("member_ids", ())
                if str(value)
            )
        )
        observable_contract = dict(metadata.get("observable_contract", {}))
        proof_ready = candidate.proof_status in {
            PROOF_SAFE_BY_EQUIVALENCE,
            PROOF_SAFE_BY_PUBLIC_FACADE,
        }
        retain_disposition = retain_by_candidate_id.get(candidate.candidate_id)
        candidate_retain_ready = bool(
            retain_disposition is not None
            and retain_disposition.basis
            in {
                "different_current_semantics",
                "independent_validation_roles",
            }
            and retain_disposition.member_ids == member_ids
        )
        necessary_uncalled_rows = tuple(
            current_necessity_by_member_id.get(member_id)
            for member_id in member_ids
        )
        necessary_uncalled_retain_ready = bool(
            signal == "unreferenced_helper"
            and member_ids
            and all(row is not None for row in necessary_uncalled_rows)
        )
        retain_ready = bool(
            candidate_retain_ready
            or necessary_uncalled_retain_ready
        )
        retain_rows = (
            (retain_disposition,)
            if candidate_retain_ready
            and retain_disposition is not None
            else tuple(
                sorted(
                    {
                        row.disposition_id: row
                        for row in necessary_uncalled_rows
                        if row is not None
                    }.values(),
                    key=lambda row: row.disposition_id,
                )
            )
            if necessary_uncalled_retain_ready
            else ()
        )
        if proof_ready and candidate.target_action == TARGET_ACTION_MERGE:
            action = STEP_ACTION_MERGE
        elif proof_ready and candidate.target_action in {
            TARGET_ACTION_COLLAPSE,
            TARGET_ACTION_KEEP_FACADE,
        }:
            action = STEP_ACTION_DELEGATE
        elif proof_ready and candidate.target_action == TARGET_ACTION_REMOVE:
            action = STEP_ACTION_REMOVE
        elif retain_ready:
            action = STEP_ACTION_RETAIN
        else:
            action = STEP_ACTION_UNRESOLVED

        if action == STEP_ACTION_MERGE:
            replacement_step_ids = (candidate.code_node_id,)
        elif action == STEP_ACTION_DELEGATE:
            replacement_step_ids = tuple(
                value
                for value in (
                    candidate.delegates_to_code_contract_id,
                    candidate.owner_code_contract_id,
                    candidate.code_node_id,
                )
                if value
            )[:1]
        elif action == STEP_ACTION_REMOVE and metadata.get("caller_ids"):
            replacement_step_ids = tuple(
                value for value in member_ids if value != candidate.code_node_id
            )[:1]
        else:
            replacement_step_ids = ()

        observable_safety_responsibilities = {
            *(
                f"behavior:{value}"
                for value in observable_contract.get("behavior_block_ids", ())
                if str(value)
            ),
            *(
                f"state:{value}"
                for key in ("state_reads", "state_writes")
                for value in observable_contract.get(key, ())
                if str(value)
            ),
            *(
                f"effect:{value}"
                for value in observable_contract.get("side_effect_ids", ())
                if str(value)
            ),
            *(
                f"error:{value}"
                for value in observable_contract.get("raised_error_ids", ())
                if str(value)
            ),
        }
        evidence_neighborhood_id = str(
            observable_contract.get("evidence_neighborhood_id", "")
        )
        if evidence_neighborhood_id:
            observable_safety_responsibilities.add(
                "evidence-neighborhood:" + evidence_neighborhood_id
            )
        retain_member_owner_bindings = {
            member_id: owner_id
            for row in retain_rows
            for member_id, owner_id in row.member_owner_bindings
            if member_id in member_ids
        }
        if retain_ready:
            safety_owner_bindings = {
                "retained-member:" + member_id: owner_id
                for member_id, owner_id in retain_member_owner_bindings.items()
            }
            safety_responsibility_ids = tuple(sorted(safety_owner_bindings))
        else:
            safety_responsibility_ids = tuple(
                sorted(observable_safety_responsibilities)
            )
        post_action_owner = (
            candidate.owner_code_contract_id
            or next(
                iter(observable_contract.get("owner_ids", ())),
                "",
            )
        )
        if not retain_ready:
            safety_owner_bindings = (
                {
                    responsibility_id: post_action_owner
                    for responsibility_id in safety_responsibility_ids
                }
                if proof_ready and post_action_owner
                else {}
            )
        raw_cost = metadata.get("step_cost_evidence")
        cost_evidence = (
            (ArchitectureReductionStepCost.from_dict(raw_cost),)
            if isinstance(raw_cost, dict)
            else ()
        )
        unresolved_gaps = tuple(
            sorted(
                {
                    *(
                        str(value)
                        for value in metadata.get(
                            "missing_proof_obligations", ()
                        )
                        if str(value)
                    ),
                    *(
                        str(value)
                        for value in metadata.get(
                            "caller_resolution_gap_ids", ()
                        )
                        if str(value)
                    ),
                }
            )
        )
        if action == STEP_ACTION_UNRESOLVED and not unresolved_gaps:
            unresolved_gaps = ("current_step_action_proof",)
        assessment_seed = {
            "candidate_id": candidate.candidate_id,
            "signal": signal,
            "member_ids": member_ids,
            "action": action,
        }
        rows.append(
            ArchitectureReductionStepAssessment(
                assessment_id=(
                    "self-step-assessment:"
                    + fingerprint_value(assessment_seed).split(":", 1)[1]
                ),
                parent_route_id="flowguard:self-maintenance",
                step_id="candidate-step:" + candidate.candidate_id,
                step_kind=step_kind_by_signal.get(signal, STEP_KIND_OTHER),
                action=action,
                proof_status=candidate.proof_status,
                rationale=(
                    "Current equivalence and owner evidence supports this exact "
                    "internal-step action."
                    if proof_ready
                    else "The model implementation and its independent checker "
                    "must not share the helper that defines the checked operation."
                    if retain_disposition is not None
                    and retain_disposition.basis == "independent_validation_roles"
                    else "Different source-independent current semantic obligations "
                    "require these structurally similar members to remain independently owned."
                    if candidate_retain_ready
                    else "Every helper has a direct-current necessity witness, so the "
                    "absence of a bounded static caller does not make it removable."
                    if necessary_uncalled_retain_ready
                    else "The existing self inventory exposes this internal-step "
                    "cost and structure, but missing proof keeps its action unresolved."
                ),
                candidate_id=candidate.candidate_id,
                current_owner_ids=tuple(
                    sorted(
                        set(retain_member_owner_bindings.values())
                        if retain_ready
                        else {
                            str(value)
                            for value in observable_contract.get("owner_ids", ())
                            if str(value)
                        }
                    )
                ),
                necessity_evidence_refs=(
                    tuple(
                        witness.fingerprint
                        for row in retain_rows
                        for witness in row.necessity_witnesses
                    )
                    if retain_ready
                    else ()
                ),
                equivalence_evidence_refs=(
                    candidate.evidence_refs if proof_ready else ()
                ),
                caller_ids=tuple(metadata.get("caller_ids", ())),
                caller_inventory_complete=not bool(
                    metadata.get("caller_resolution_gap_ids", ())
                ),
                replacement_step_ids=replacement_step_ids,
                cost_evidence=cost_evidence,
                safety_inventory_complete=bool(
                    retain_ready
                    and set(retain_member_owner_bindings) == set(member_ids)
                    or proof_ready
                    and (
                        not safety_responsibility_ids
                        or set(safety_responsibility_ids)
                        == set(safety_owner_bindings)
                    )
                ),
                safety_responsibility_ids=(
                    safety_responsibility_ids
                    if proof_ready or retain_ready
                    else ()
                ),
                safety_owner_bindings=safety_owner_bindings,
                safety_evidence_refs=(
                    candidate.evidence_refs
                    if proof_ready and safety_responsibility_ids
                    else tuple(
                        sorted(
                            {
                                evidence_fingerprint
                                for row in retain_rows
                                for evidence_fingerprint in row.evidence_fingerprints
                            }
                        )
                    )
                    if retain_ready
                    and safety_responsibility_ids
                    else ()
                ),
                unresolved_gap_ids=(
                    unresolved_gaps
                    if action == STEP_ACTION_UNRESOLVED
                    else ()
                ),
            )
        )
    return tuple(sorted(rows, key=lambda row: row.assessment_id))


def _execute_semantic_proof_owner(
    current: Any,
    root: Path,
    receipt_root: Path,
    *,
    all_contracts: tuple[ValidationOwnerContract, ...],
    subject: dict[str, Any],
    evidence_context: dict[str, Any],
    child_id: str,
    summary: str,
    claim_boundary: str,
) -> Any:
    """Publish only after the authentic process output proves exact semantics."""

    supervised = run_supervised(
        current.contract.command,
        cwd=root,
        timeout_seconds=current.contract.timeout_seconds,
    )
    if not supervised.ok:
        raise ValueError(
            "self reduction semantic proof owner did not reach a clean terminal pass: "
            + supervised.terminal_reason
        )
    if supervised.stderr:
        raise ValueError(
            "self reduction semantic proof owner emitted non-canonical stderr"
        )
    semantic_result = _parse_semantic_execution_stdout(
        supervised.stdout,
        subject,
    )
    execution = publish_supervised_validation_owner_result(
        current,
        supervised,
        root,
        receipt_root,
        all_contracts=all_contracts,
        child_id=child_id,
        evidence_context={
            **evidence_context,
            "execution_result": semantic_result,
        },
        summary=summary,
        claim_boundary=claim_boundary,
    )
    if not execution.ok:
        raise ValueError(
            "self reduction semantic proof owner did not publish a green receipt: "
            + execution.blocker
        )
    return execution


def _reuse_or_execute_semantic_proof_owner(
    current: Any,
    root: Path,
    receipt_root: Path,
    *,
    all_contracts: tuple[ValidationOwnerContract, ...],
    subject: dict[str, Any],
    evidence_context: dict[str, Any],
    child_id: str,
    summary: str,
    claim_boundary: str,
) -> tuple[EvidenceReceipt, ReceiptVerificationResult]:
    """Reuse one exact leaf before executing the missing owner."""

    receipt, verification = find_reusable_owner_receipt(
        current,
        root,
        receipt_root,
    )
    if receipt is not None and verification is not None and verification.ok:
        _verified_leaf_execution(
            receipt_root,
            receipt,
            evidence_context,
            subject,
        )
        return receipt, verification
    execution = _execute_semantic_proof_owner(
        current,
        root,
        receipt_root,
        all_contracts=all_contracts,
        subject=subject,
        evidence_context=evidence_context,
        child_id=child_id,
        summary=summary,
        claim_boundary=claim_boundary,
    )
    assert execution.receipt is not None
    assert execution.verification is not None
    return execution.receipt, execution.verification


def _execute_frozen_self_reduction_proof(
    root_path: Path,
    receipt_root: Path,
    bundle: FlowGuardSelfBlueprintBundle,
    candidate: ArchitectureReductionCandidate,
    proof_payload: dict[str, Any],
    ordered: tuple[ValidationOwnerContract, ...],
    currents: Mapping[str, Any],
) -> SelfReductionProofRecord:
    """Execute one prepared row without rebuilding or rediscovering the batch."""

    contracts = _proof_contracts(bundle, candidate, proof_payload)
    test_contract, parity_contract, aggregate_contract = contracts
    test_context, parity_context = _leaf_evidence_contexts(
        bundle,
        candidate,
        proof_payload,
    )
    test_subject, parity_subject = _proof_execution_subjects(bundle, candidate)
    test_receipt, _test_verification = _reuse_or_execute_semantic_proof_owner(
        currents[test_contract.owner_id],
        root_path,
        receipt_root,
        all_contracts=ordered,
        subject=test_subject,
        child_id=f"child:{test_contract.owner_id}",
        evidence_context=test_context,
        summary="Exact current candidate tests completed under supervision.",
        claim_boundary="Exact candidate test nodes and coverage only.",
    )
    parity_receipt, _parity_verification = _reuse_or_execute_semantic_proof_owner(
        currents[parity_contract.owner_id],
        root_path,
        receipt_root,
        all_contracts=ordered,
        subject=parity_subject,
        child_id=f"child:{parity_contract.owner_id}",
        evidence_context=parity_context,
        summary="Exact current candidate parity checks completed under supervision.",
        claim_boundary=(
            "Caller/consumer, state, side-effect, and error parity for one candidate."
        ),
    )
    aggregate_receipt, _ = save_child_bound_owner_receipt(
        currents[aggregate_contract.owner_id],
        (test_receipt, parity_receipt),
        root_path,
        receipt_root,
        all_contracts=ordered,
        child_contracts=(test_contract, parity_contract),
        started_at=min(test_receipt.started_at, parity_receipt.started_at),
        finished_at=max(test_receipt.finished_at, parity_receipt.finished_at),
        evidence_context=_aggregate_evidence_context(
            proof_payload,
            test_receipt,
            parity_receipt,
        ),
        claim_boundary=(
            "One exact self-reduction candidate, its current mapped tests, and four parity obligations."
        ),
    )
    record = SelfReductionProofRecord.from_canonical_evidence_payload(
        proof_payload,
        aggregate_receipt_id=aggregate_receipt.receipt_id,
    )
    _verify_one_proof_record(
        root_path,
        receipt_root,
        bundle,
        candidate,
        record,
    )
    return record


def execute_flowguard_self_reduction_proofs(
    root: str = ".",
    *,
    expected_candidate_inventory_fingerprint: str,
    selections: tuple[SelfReductionProofSelection, ...],
) -> tuple[SelfReductionProofRecord, ...]:
    """Execute one frozen candidate batch, reusing exact-current proof owners first."""

    if (
        not isinstance(expected_candidate_inventory_fingerprint, str)
        or not expected_candidate_inventory_fingerprint
    ):
        raise ValueError(
            "self reduction proof batch requires the expected candidate inventory fingerprint"
        )
    if not isinstance(selections, tuple) or any(
        not isinstance(selection, SelfReductionProofSelection)
        for selection in selections
    ):
        raise TypeError(
            "self reduction proof batch requires typed SelfReductionProofSelection rows"
        )
    if not selections:
        raise ValueError("self reduction proof batch requires at least one selection")
    ordered_selections = tuple(
        sorted(selections, key=lambda selection: selection.candidate_id)
    )
    selected_candidate_ids = tuple(
        selection.candidate_id for selection in ordered_selections
    )
    if len(selected_candidate_ids) != len(set(selected_candidate_ids)):
        raise ValueError(
            "self reduction proof batch contains duplicate candidate selections"
        )

    root_path = _resolved_repository_root(root)
    bundle = build_flowguard_self_blueprint(root_path)
    build_input_identity = getattr(bundle, "build_input_identity", None)
    if not isinstance(build_input_identity, SelfBlueprintBuildInputIdentity):
        raise TypeError(
            "self reduction proof batch requires the typed identity carried by its one blueprint build"
        )
    universe = derive_self_reduction_universe(bundle, root=root_path)
    candidates, inventory_fingerprint, _, _ = _self_reduction_candidates(
        bundle,
        root=root_path,
        reduction_universe=universe,
        proof_records=(),
    )
    if inventory_fingerprint != expected_candidate_inventory_fingerprint:
        raise ValueError(
            "self reduction proof selection inventory is stale for the current frozen batch"
        )
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    current_proofs, _ = _discover_current_self_reduction_proofs(
        root_path,
        bundle,
        candidates,
    )
    current_proof_by_candidate_id = {
        proof.candidate_id: proof for proof in current_proofs
    }
    receipt_root = _canonical_validation_owner_root(root_path)
    prepared: list[
        tuple[
            ArchitectureReductionCandidate,
            dict[str, Any],
            tuple[ValidationOwnerContract, ...],
            dict[str, Any],
        ]
    ] = []
    records: list[SelfReductionProofRecord] = []

    for selection in ordered_selections:
        candidate = candidate_by_id.get(selection.candidate_id)
        if candidate is None:
            raise ValueError(
                "self reduction proof selection references no exact current candidate"
            )
        binding = _candidate_binding(candidate)
        if binding.fingerprint != selection.candidate_fingerprint:
            raise ValueError(
                "self reduction proof selection candidate fingerprint is stale"
            )
        proof_payload = _self_reduction_proof_payload(
            root_path,
            bundle,
            candidate,
            selection.proof_status,
        )
        existing = current_proof_by_candidate_id.get(candidate.candidate_id)
        if existing is not None:
            if existing.record.canonical_evidence_payload != proof_payload:
                raise ValueError(
                    "candidate already has a different exact-current self reduction proof"
                )
            records.append(existing.record)
            continue
        contracts = _proof_contracts(bundle, candidate, proof_payload)
        ordered = topological_owner_contracts(contracts)
        currents = {
            contract.owner_id: build_owner_current(
                root_path,
                contract,
                all_contracts=ordered,
            )
            for contract in ordered
        }
        prepared.append((candidate, proof_payload, ordered, currents))

    for candidate, proof_payload, ordered, currents in prepared:
        records.append(
            _execute_frozen_self_reduction_proof(
                root_path,
                receipt_root,
                bundle,
                candidate,
                proof_payload,
                ordered,
                currents,
            )
        )

    verified = _verify_proof_records(
        root_path,
        bundle,
        candidates,
        tuple(sorted(records, key=lambda record: record.candidate_id)),
    )
    _recheck_verified_proof_currentness(root_path, verified)
    if (
        capture_flowguard_self_blueprint_build_input_identity(root_path)
        != build_input_identity
    ):
        raise ValueError(
            "self-blueprint build inputs changed before proof batch publication completed"
        )
    return tuple(proof.record for proof in verified)


def _self_reduction_completion_status(
    *,
    blueprint_ok: bool,
    reduction_report_ok: bool,
    denominator_complete: bool,
    audit_accounted: bool,
    candidate_review_complete: bool,
    step_decision_complete: bool,
    unresolved_member_ids: tuple[str, ...],
    unresolved_step_ids: tuple[str, ...],
    action_authorized_candidate_ids: tuple[str, ...],
) -> tuple[bool, bool, str]:
    """Keep audit completion, pending action, and cleanup closure distinct."""

    audit_complete = bool(
        blueprint_ok
        and reduction_report_ok
        and denominator_complete
        and audit_accounted
    )
    cleanup_release_ready = bool(
        audit_complete
        and candidate_review_complete
        and step_decision_complete
        and not unresolved_member_ids
        and not unresolved_step_ids
        and not action_authorized_candidate_ids
    )
    status = (
        "pass"
        if audit_complete and not action_authorized_candidate_ids
        else "blocked"
    )
    return audit_complete, cleanup_release_ready, status


def _review_current_flowguard_self_architecture_reduction(
    root: str = ".",
    *,
    bundle: FlowGuardSelfBlueprintBundle,
    build_input_identity: SelfBlueprintBuildInputIdentity | None = None,
) -> SelfArchitectureReductionReview:
    """Review one bundle that was built from ``root`` by a trusted caller."""

    bundle_build_input_identity = getattr(bundle, "build_input_identity", None)
    if build_input_identity is None:
        build_input_identity = bundle_build_input_identity
    if not isinstance(build_input_identity, SelfBlueprintBuildInputIdentity):
        raise TypeError(
            "self architecture reduction requires the typed input identity carried by its build"
        )
    if (
        isinstance(bundle_build_input_identity, SelfBlueprintBuildInputIdentity)
        and bundle_build_input_identity != build_input_identity
    ):
        raise ValueError(
            "self architecture reduction build identity differs from its exact bundle"
        )
    _canonical_validation_owner_root(root)
    raw_reduction_universe = derive_self_reduction_universe(bundle, root=root)
    (
        initial_candidates,
        initial_inventory_fingerprint,
        initial_compatibility_classifications,
        initial_evidence_neighborhood_catalog,
    ) = _self_reduction_candidates(
        bundle,
        root=root,
        reduction_universe=raw_reduction_universe,
        proof_records=(),
    )
    candidate_bindings = tuple(
        _candidate_binding(candidate) for candidate in initial_candidates
    )
    external_commitment_bindings = (
        _derive_current_external_commitment_bindings(root, bundle)
    )
    necessity_gaps_by_member: dict[str, tuple[str, ...]] = {}
    retain_dispositions = derive_self_reduction_retain_dispositions(
        bundle,
        raw_reduction_universe,
        candidate_bindings=candidate_bindings,
        external_commitment_bindings=external_commitment_bindings,
        necessity_gap_sink=necessity_gaps_by_member,
    )
    verified_proofs, historical_proof_receipt_ids = (
        _discover_current_self_reduction_proofs(
            root,
            bundle,
            initial_candidates,
        )
    )
    proof_ids = tuple(proof.proof_id for proof in verified_proofs)
    if verified_proofs:
        (
            candidates,
            inventory_fingerprint,
            compatibility_classifications,
            evidence_neighborhood_catalog,
        ) = _self_reduction_candidates(
            bundle,
            root=root,
            reduction_universe=raw_reduction_universe,
            proof_records=verified_proofs,
        )
        if (
            inventory_fingerprint != initial_inventory_fingerprint
            or tuple(row.candidate_id for row in candidates)
            != tuple(row.candidate_id for row in initial_candidates)
            or tuple(row.to_dict() for row in compatibility_classifications)
            != tuple(
                row.to_dict() for row in initial_compatibility_classifications
            )
            or evidence_neighborhood_catalog.fingerprint
            != initial_evidence_neighborhood_catalog.fingerprint
            or evidence_neighborhood_catalog.to_dict()
            != initial_evidence_neighborhood_catalog.to_dict()
        ):
            raise ValueError(
                "self reduction proof changed the independently discovered candidate inventory"
            )
    else:
        candidates = initial_candidates
        inventory_fingerprint = initial_inventory_fingerprint
        compatibility_classifications = initial_compatibility_classifications
        evidence_neighborhood_catalog = (
            initial_evidence_neighborhood_catalog
        )
    proof_registry_fingerprint = fingerprint_value(
        {
            "schema_version": "flowguard.self_reduction_proof_registry.v2",
            "proofs": [row.to_dict() for row in verified_proofs],
            "historical_aggregate_receipt_ids": list(
                historical_proof_receipt_ids
            ),
        }
    )
    retain_registry_fingerprint = fingerprint_value(
        {
            "schema_version": "flowguard.self_reduction_retain_registry.v1",
            "subject_revision": bundle.inventory.boundary.subject_revision,
            "implementation_inventory_fingerprint": (
                bundle.inventory.inventory_fingerprint
            ),
            "test_inventory_fingerprint": (
                bundle.test_inventory.inventory_fingerprint
            ),
            "universe_fingerprint": raw_reduction_universe.fingerprint,
            "dispositions": [row.to_dict() for row in retain_dispositions],
        }
    )
    entrypoints = tuple(
        sorted(
            row.surface_id
            for row in bundle.inventory.surfaces
            if "entrypoint" in row.roles or row.surface_kind == "entrypoint"
        )
    ) or ("flowguard.public_api", "python -m flowguard")
    step_assessments = _self_step_assessments(
        candidates,
        retain_dispositions,
    )
    plan = ArchitectureReductionPlan(
        reduction_id="flowguard:self-architecture-reduction",
        observable_contract=ObservableArchitectureContract(
            source_model_id=bundle.manifest.fingerprint,
            source_code_boundary_id=bundle.inventory.inventory_fingerprint,
            public_entrypoints=entrypoints,
            observable_outputs=(
                "flowguard.self_blueprint.bundle",
                "flowguard.cli.machine_output",
            ),
            observable_state=(
                "observed_model_authority",
                "current_evidence_pointers",
            ),
            observable_side_effects=("explicit_command_owned_writes",),
            validation_boundaries=(
                bundle.qualification.fingerprint,
                bundle.static_readiness.fingerprint,
            ),
            rationale=(
                "Any contraction must preserve the exact current self-blueprint, "
                "public entrypoints, machine output, state authority, and evidence gates."
            ),
        ),
        candidates=candidates,
        compatibility_surfaces=compatibility_classifications,
        companion_route_triggers=(
            ArchitectureReductionTrigger(
                route_id=ROUTE_STRUCTURE_MESH,
                trigger_reason=(
                    "The self-blueprint inventory independently reports module size "
                    "and repeated behavior-shape signals."
                ),
                complexity_signal="self_blueprint_candidate_inventory",
                recommended_timing="before release completion",
            ),
            ArchitectureReductionTrigger(
                route_id=ROUTE_DEVELOPMENT_PROCESS_FLOW,
                trigger_reason=(
                    "Any applied self contraction changes the staged maintenance "
                    "and release evidence boundary, even when runtime behavior is preserved."
                ),
                complexity_signal="self_reduction_lifecycle_and_release_boundary",
                recommended_timing="before applying a proof-ready contraction",
            ),
        ),
        rationale=(
            "Use the exact self blueprint to prevent unchecked architectural growth "
            "without treating resemblance as proof or rewriting code automatically."
        ),
        inventory_revision=inventory_fingerprint,
        inventory_source_ref=(
            "self-blueprint:" + bundle.inventory.inventory_fingerprint
        ),
        inventory_current=True,
        expected_candidate_ids=tuple(row.candidate_id for row in candidates),
        require_complete_inventory=True,
        step_assessments=step_assessments,
    )
    reduction_report = review_architecture_reduction(plan)
    ready_candidate_ids = set(reduction_report.ready_candidate_ids)
    contract_signal_ids = {
        str(signal_id)
        for candidate in candidates
        if candidate.candidate_id in ready_candidate_ids
        for signal_id in candidate.metadata.get("source_signal_ids", ())
        if str(signal_id)
    }
    ready_step_action_by_signal: dict[str, str] = {}
    for candidate in candidates:
        if candidate.candidate_id not in ready_candidate_ids:
            continue
        if candidate.target_action == TARGET_ACTION_MERGE:
            step_action = STEP_ACTION_MERGE
        elif candidate.target_action in {
            TARGET_ACTION_COLLAPSE,
            TARGET_ACTION_KEEP_FACADE,
        }:
            step_action = STEP_ACTION_DELEGATE
        elif candidate.target_action == TARGET_ACTION_REMOVE:
            step_action = STEP_ACTION_REMOVE
        else:
            continue
        for signal_id in candidate.metadata.get("source_signal_ids", ()):
            signal_key = str(signal_id)
            existing = ready_step_action_by_signal.get(signal_key)
            if existing is not None and existing != step_action:
                raise ValueError(
                    "one self-reduction signal received conflicting ready step actions"
                )
            ready_step_action_by_signal[signal_key] = step_action
    contract_surface_ids = {
        str(member_id)
        for candidate in candidates
        if candidate.candidate_id in ready_candidate_ids
        and candidate.proof_status == PROOF_SAFE_BY_EQUIVALENCE
        for member_id in candidate.metadata.get("member_ids", ())
        if str(member_id)
    }
    contract_member_ids = contract_signal_ids | contract_surface_ids
    unresolved_source_gap_ids = set(raw_reduction_universe.source_gap_ids)
    retain_by_member: dict[str, SelfReductionRetainDisposition] = {}
    raw_member_ids = {row.member_id for row in raw_reduction_universe.members}
    for disposition in retain_dispositions:
        if (
            disposition.subject_revision
            != bundle.inventory.boundary.subject_revision
            or disposition.implementation_inventory_fingerprint
            != bundle.inventory.inventory_fingerprint
            or disposition.test_inventory_fingerprint
            != bundle.test_inventory.inventory_fingerprint
            or disposition.universe_fingerprint
            != raw_reduction_universe.fingerprint
        ):
            raise ValueError(
                "retain disposition is stale for the current self reduction universe"
            )
        if disposition.candidate_ids:
            continue
        for member_id in disposition.member_ids:
            if member_id not in raw_member_ids:
                raise ValueError(
                    f"retain disposition references an unknown member: {member_id}"
                )
            if member_id in unresolved_source_gap_ids:
                raise ValueError(
                    "retain disposition cannot close an unresolved source gap"
                )
            if member_id in retain_by_member:
                raise ValueError(
                    f"multiple retain authorities cover one member: {member_id}"
                )
            retain_by_member[member_id] = disposition
    reduction_universe = replace(
        raw_reduction_universe,
        members=tuple(
            replace(
                row,
                disposition=(
                    "contract"
                    if row.member_id in contract_member_ids
                    else "unresolved"
                    if row.member_id in unresolved_source_gap_ids
                    else "retain"
                    if row.member_id in retain_by_member
                    else "unresolved"
                ),
                rationale=(
                    "An exact-current leaf-owner proof closes this member for a pending behavior-preserving contraction."
                    if row.member_id in contract_member_ids
                    else row.rationale
                    if row.member_id in unresolved_source_gap_ids
                    else retain_by_member[row.member_id].rationale
                    if row.member_id in retain_by_member
                    else row.rationale
                ),
                step_action=(
                    ready_step_action_by_signal[row.member_id]
                    if row.member_id in ready_step_action_by_signal
                    else STEP_ACTION_UNRESOLVED
                    if row.step_action
                    and row.member_id in unresolved_source_gap_ids
                    else STEP_ACTION_RETAIN
                    if row.step_action and row.member_id in retain_by_member
                    else STEP_ACTION_UNRESOLVED
                    if row.step_action
                    else ""
                ),
            )
            for row in raw_reduction_universe.members
        ),
        universe_fingerprint="",
    )
    expected = tuple(sorted(row.candidate_id for row in candidates))
    covered = tuple(sorted(reduction_report.covered_candidate_ids))
    universe_surface_ids = set(reduction_universe.implementation_surface_ids)
    candidate_surface_ids = {
        str(member_id)
        for candidate in candidates
        for member_id in candidate.metadata.get("member_ids", ())
        if str(member_id)
    }
    known_signal_ids = set(reduction_universe.reduction_signal_ids)
    candidate_signal_ids = {
        str(signal_id)
        for candidate in candidates
        for signal_id in candidate.metadata.get("source_signal_ids", ())
        if str(signal_id)
    }
    ready_signal_ids = {
        str(signal_id)
        for candidate in candidates
        if candidate.candidate_id in ready_candidate_ids
        for signal_id in candidate.metadata.get("source_signal_ids", ())
        if str(signal_id)
    }
    proof_keys = {
        (proof.candidate_signal, proof.member_ids) for proof in verified_proofs
    }
    candidate_keys = {
        (
            str(candidate.metadata.get("signal", "")),
            tuple(
                sorted(
                    str(value)
                    for value in candidate.metadata.get("member_ids", ())
                    if str(value)
                )
            ),
        )
        for candidate in candidates
    }
    used_proof_ids = {
        str(candidate.metadata.get("proof_record_id", ""))
        for candidate in candidates
        if str(candidate.metadata.get("proof_record_id", ""))
    }
    candidate_inventory_independent = bool(
        inventory_fingerprint != raw_reduction_universe.fingerprint
        and candidate_signal_ids <= known_signal_ids
        and proof_keys <= candidate_keys
        and used_proof_ids == set(proof_ids)
        and all(proof.fingerprint != inventory_fingerprint for proof in verified_proofs)
        and all(
            disposition.fingerprint
            not in {inventory_fingerprint, raw_reduction_universe.fingerprint}
            for disposition in retain_dispositions
        )
    )
    denominator_complete = reduction_universe.complete
    decision_required_ids = set(reduction_universe.implementation_surface_ids) | set(
        reduction_universe.reduction_signal_ids
    )
    independently_disposed_ids = set(contract_signal_ids) | set(
        contract_surface_ids
    ) | set(retain_by_member)
    candidate_review_complete = (
        expected == covered
        and candidate_surface_ids <= universe_surface_ids
        and candidate_inventory_independent
        and all(candidate.metadata.get("source_signal_ids", ()) for candidate in candidates)
        and contract_signal_ids == ready_signal_ids
        and decision_required_ids <= independently_disposed_ids
    )
    safe_unapplied = tuple(sorted(ready_candidate_ids))
    unresolved_member_ids = tuple(
        sorted(
            row.member_id
            for row in reduction_universe.members
            if row.disposition == "unresolved"
        )
    )
    necessity_gap_members_by_kind: dict[str, list[str]] = {}
    unresolved_member_id_set = set(unresolved_member_ids)
    for member_id, gap_ids in necessity_gaps_by_member.items():
        if member_id not in unresolved_member_id_set:
            continue
        for gap_id in gap_ids:
            necessity_gap_members_by_kind.setdefault(gap_id, []).append(
                member_id
            )
    necessity_gap_counts_by_kind = tuple(
        (gap_id, len(set(member_ids)))
        for gap_id, member_ids in sorted(necessity_gap_members_by_kind.items())
    )
    necessity_gap_examples_by_kind = tuple(
        (gap_id, tuple(sorted(set(member_ids)))[:8])
        for gap_id, member_ids in sorted(necessity_gap_members_by_kind.items())
    )
    unresolved_step_ids = tuple(
        sorted(
            row.step_id
            for row in reduction_report.step_assessments
            if row.action == STEP_ACTION_UNRESOLVED
        )
    )
    assessed_candidate_ids = {
        row.candidate_id
        for row in reduction_report.step_assessments
        if row.candidate_id
    }
    step_decision_complete = bool(
        assessed_candidate_ids == set(expected)
        and len(reduction_report.step_assessments) == len(candidates)
        and not unresolved_step_ids
    )
    member_ids = {row.member_id for row in reduction_universe.members}
    audit_accounted = bool(
        candidate_inventory_independent
        and expected == covered
        and candidate_surface_ids <= universe_surface_ids
        and all(candidate.metadata.get("source_signal_ids", ()) for candidate in candidates)
        and contract_signal_ids == ready_signal_ids
        and set(raw_reduction_universe.required_implementation_surface_ids)
        == set(raw_reduction_universe.implementation_surface_ids)
        and set(raw_reduction_universe.source_gap_ids) <= member_ids
        and all(
            row.disposition in SELF_REDUCTION_DISPOSITIONS
            for row in reduction_universe.members
        )
    )
    action_authorized_candidate_ids = tuple(sorted(ready_candidate_ids))
    (
        audit_complete,
        cleanup_release_ready,
        status,
    ) = _self_reduction_completion_status(
        blueprint_ok=bundle.ok,
        reduction_report_ok=reduction_report.ok,
        denominator_complete=denominator_complete,
        audit_accounted=audit_accounted,
        candidate_review_complete=candidate_review_complete,
        step_decision_complete=step_decision_complete,
        unresolved_member_ids=unresolved_member_ids,
        unresolved_step_ids=unresolved_step_ids,
        action_authorized_candidate_ids=action_authorized_candidate_ids,
    )
    _recheck_verified_proof_currentness(root, verified_proofs)
    fresh_build_input_identity = (
        capture_flowguard_self_blueprint_build_input_identity(root)
    )
    if fresh_build_input_identity != build_input_identity:
        raise ValueError(
            "self-blueprint build inputs changed before architecture-reduction review publication"
        )
    return SelfArchitectureReductionReview(
        self_blueprint_fingerprint=bundle.manifest.fingerprint,
        implementation_inventory_fingerprint=bundle.inventory.inventory_fingerprint,
        behavior_report_fingerprint=bundle.behavior_report.fingerprint,
        reduction_universe=reduction_universe,
        reduction_universe_fingerprint=reduction_universe.fingerprint,
        candidate_inventory_fingerprint=inventory_fingerprint,
        candidate_evidence_neighborhood_catalog=(
            evidence_neighborhood_catalog
        ),
        candidate_evidence_neighborhood_catalog_fingerprint=(
            evidence_neighborhood_catalog.fingerprint
        ),
        proof_registry_fingerprint=proof_registry_fingerprint,
        retain_registry_fingerprint=retain_registry_fingerprint,
        retain_dispositions=retain_dispositions,
        candidates=candidates,
        compatibility_classifications=compatibility_classifications,
        reduction_report=reduction_report,
        denominator_complete=denominator_complete,
        candidate_review_complete=candidate_review_complete,
        step_decision_complete=step_decision_complete,
        candidate_inventory_independent=candidate_inventory_independent,
        audit_accounted=audit_accounted,
        audit_complete=audit_complete,
        action_authorized_candidate_ids=action_authorized_candidate_ids,
        cleanup_release_ready=cleanup_release_ready,
        necessity_gap_counts_by_kind=necessity_gap_counts_by_kind,
        necessity_gap_examples_by_kind=necessity_gap_examples_by_kind,
        unresolved_member_ids=unresolved_member_ids,
        unresolved_step_ids=unresolved_step_ids,
        safe_unapplied_candidate_ids=safe_unapplied,
        status=status,
    )


def review_flowguard_self_architecture_reduction(
    root: str = ".",
) -> SelfArchitectureReductionReview:
    """Standalone direct path: build one bundle and review that exact bundle."""

    bundle = build_flowguard_self_blueprint(root)
    return _review_current_flowguard_self_architecture_reduction(
        root,
        bundle=bundle,
        build_input_identity=bundle.build_input_identity,
    )


def build_flowguard_self_architecture_reduction_review(
    root: str = ".",
) -> tuple[FlowGuardSelfBlueprintBundle, SelfArchitectureReductionReview]:
    """Use one authoritative bundle plus one final currentness comparator."""

    bundle = build_flowguard_self_blueprint(root)
    review = _review_current_flowguard_self_architecture_reduction(
        root,
        bundle=bundle,
        build_input_identity=bundle.build_input_identity,
    )
    return bundle, review


__all__ = [
    "SELF_ARCHITECTURE_REDUCTION_SCHEMA",
    "SELF_REDUCTION_CANDIDATE_INVENTORY_SCHEMA",
    "SELF_REDUCTION_EVIDENCE_NEIGHBORHOOD_CATALOG_SCHEMA",
    "SELF_REDUCTION_EVIDENCE_NEIGHBORHOOD_SCHEMA",
    "SELF_REDUCTION_OBSERVABLE_CONTRACT_SCHEMA",
    "SELF_REDUCTION_PARITY_OBLIGATION_IDS",
    "SELF_REDUCTION_PROOF_RECORD_SCHEMA",
    "SelfArchitectureReductionReview",
    "SelfReductionEvidenceNeighborhood",
    "SelfReductionEvidenceNeighborhoodCatalog",
    "SelfReductionProofRecord",
    "SelfReductionProofSelection",
    "SelfReductionRetainDisposition",
    "build_flowguard_self_architecture_reduction_review",
    "execute_flowguard_self_reduction_proofs",
    "review_flowguard_self_architecture_reduction",
    "self_reduction_proof_obligation_ids",
    "self_reduction_proof_projected_inputs",
]
