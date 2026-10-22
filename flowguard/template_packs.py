"""Portable route-scoped template seeds with bounded predicates and exact selection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence


PREDICATE_OPERATORS = ("equals", "one_of", "contains", "contains_all", "exists")

_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))

# A seed is a portable, reviewable branch of model knowledge.  It is kept
# separate from the file-template pack so a consumer projection can never
# mistake generated starter files for target-owned semantic truth.
TEMPLATE_SEED_SCHEMA = "flowguard.template-seed.v1"
TEMPLATE_SEED_PROMOTION_STATUSES = ("candidate", "promoted", "retired")
TEMPLATE_SEED_PRIVACY_DISPOSITIONS = ("portable_public", "private_blocked")
TEMPLATE_SEED_CLOSURE_DISPOSITIONS = ("pending", "modeled", "not_applicable")


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            frozen[key] = _freeze_json(item)
        return MappingProxyType(dict(sorted(frozen.items())))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, _JSON_SCALAR_TYPES):
        # Reject NaN and infinities through the same canonical JSON boundary.
        json.dumps(value, allow_nan=False)
        return value
    raise TypeError(f"value is not JSON-compatible: {type(value).__name__}")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _thaw_json(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _json_equal(left: Any, right: Any) -> bool:
    return _canonical_json(left) == _canonical_json(right)


def _json_mapping(value: Mapping[str, Any], *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a JSON object")
    frozen = _freeze_json(value)
    if not isinstance(frozen, Mapping):  # pragma: no cover - guarded above
        raise TypeError(f"{label} must be a JSON object")
    return frozen


@dataclass(frozen=True)
class HardPredicate:
    """One bounded predicate over a top-level selection-context key."""

    key: str
    operator: str
    expected: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", str(self.key).strip())
        object.__setattr__(self, "operator", str(self.operator).strip().lower())
        object.__setattr__(self, "expected", _freeze_json(self.expected))

    def to_dict(self) -> dict[str, Any]:
        expected = _thaw_json(self.expected)
        if self.operator in ("one_of", "contains_all") and isinstance(expected, list):
            expected = sorted(expected, key=_canonical_json)
        return {
            "key": self.key,
            "operator": self.operator,
            "expected": expected,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HardPredicate":
        return cls(
            key=str(data.get("key", "")),
            operator=str(data.get("operator", "")),
            expected=data.get("expected"),
        )


def _seed_texts(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _seed_contains_private_value(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_seed_contains_private_value(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return any(_seed_contains_private_value(item) for item in value)
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return (
        ":\\" in value
        or lowered.startswith("/users/")
        or lowered.startswith("/home/")
        or "customer_name" in lowered
        or "private_path" in lowered
    )


def _seed_contains_self_owner_identifier(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_seed_contains_self_owner_identifier(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return any(_seed_contains_self_owner_identifier(item) for item in value)
    if not isinstance(value, str):
        return False
    tokens = {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}
    return "flowguard" in tokens


@dataclass(frozen=True)
class TemplateSeed:
    """Portable branch knowledge selected by exact target facts.

    The seed is deliberately not a target model or record.  It only supplies
    a compact scaffold and the obligations the target author must close.
    """

    template_id: str
    version: str
    route_ids: tuple[str, ...]
    layers: Mapping[str, Any]
    predicates: tuple[HardPredicate, ...]
    protected_error_classes: tuple[str, ...]
    required_states: tuple[str, ...]
    required_side_effects: tuple[str, ...]
    completion_evidence: tuple[str, ...]
    positive_cases: tuple[str, ...]
    known_bad_cases: tuple[str, ...]
    false_friend_cases: tuple[str, ...]
    target_fields: tuple[str, ...]
    non_applicable_disposition: str
    source_proof_refs: tuple[str, ...]
    privacy_disposition: str = "portable_public"
    promotion_status: str = "candidate"
    closure_disposition: str = "pending"
    closure_proof_ref: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "template_id", str(self.template_id).strip())
        object.__setattr__(self, "version", str(self.version).strip())
        object.__setattr__(self, "route_ids", _seed_texts(self.route_ids))
        object.__setattr__(self, "layers", _json_mapping(self.layers, label="seed layers"))
        object.__setattr__(
            self,
            "predicates",
            tuple(item if isinstance(item, HardPredicate) else HardPredicate.from_dict(item) for item in self.predicates),
        )
        for field_name in (
            "protected_error_classes",
            "required_states",
            "required_side_effects",
            "completion_evidence",
            "positive_cases",
            "known_bad_cases",
            "false_friend_cases",
            "target_fields",
            "source_proof_refs",
        ):
            object.__setattr__(self, field_name, _seed_texts(getattr(self, field_name)))
        object.__setattr__(self, "non_applicable_disposition", str(self.non_applicable_disposition).strip())
        object.__setattr__(self, "privacy_disposition", str(self.privacy_disposition).strip())
        object.__setattr__(self, "promotion_status", str(self.promotion_status).strip())
        object.__setattr__(self, "closure_disposition", str(self.closure_disposition).strip())
        object.__setattr__(self, "closure_proof_ref", str(self.closure_proof_ref).strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TEMPLATE_SEED_SCHEMA,
            "template_id": self.template_id,
            "version": self.version,
            "route_ids": list(self.route_ids),
            "layers": _thaw_json(self.layers),
            "predicates": [predicate.to_dict() for predicate in self.predicates],
            "protected_error_classes": list(self.protected_error_classes),
            "required_states": list(self.required_states),
            "required_side_effects": list(self.required_side_effects),
            "completion_evidence": list(self.completion_evidence),
            "positive_cases": list(self.positive_cases),
            "known_bad_cases": list(self.known_bad_cases),
            "false_friend_cases": list(self.false_friend_cases),
            "target_fields": list(self.target_fields),
            "non_applicable_disposition": self.non_applicable_disposition,
            "source_proof_refs": list(self.source_proof_refs),
            "privacy_disposition": self.privacy_disposition,
            "promotion_status": self.promotion_status,
            "closure_disposition": self.closure_disposition,
            "closure_proof_ref": self.closure_proof_ref,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TemplateSeed":
        if str(data.get("schema_version", "")) != TEMPLATE_SEED_SCHEMA:
            raise ValueError("template seed schema is not current")
        return cls(
            template_id=str(data.get("template_id", "")),
            version=str(data.get("version", "")),
            route_ids=tuple(data.get("route_ids", ())),
            layers=data.get("layers", {}),
            predicates=tuple(data.get("predicates", ())),
            protected_error_classes=tuple(data.get("protected_error_classes", ())),
            required_states=tuple(data.get("required_states", ())),
            required_side_effects=tuple(data.get("required_side_effects", ())),
            completion_evidence=tuple(data.get("completion_evidence", ())),
            positive_cases=tuple(data.get("positive_cases", ())),
            known_bad_cases=tuple(data.get("known_bad_cases", ())),
            false_friend_cases=tuple(data.get("false_friend_cases", ())),
            target_fields=tuple(data.get("target_fields", ())),
            non_applicable_disposition=str(data.get("non_applicable_disposition", "")),
            source_proof_refs=tuple(data.get("source_proof_refs", ())),
            privacy_disposition=str(data.get("privacy_disposition", "portable_public")),
            promotion_status=str(data.get("promotion_status", "candidate")),
            closure_disposition=str(data.get("closure_disposition", "pending")),
            closure_proof_ref=str(data.get("closure_proof_ref", "")),
        )


@dataclass(frozen=True)
class TemplateSeedValidation:
    status: str
    findings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "pass"


@dataclass(frozen=True)
class TemplateSeedSelection:
    status: str
    matched_template_ids: tuple[str, ...] = ()
    selected_template_ids: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "selected"


def validate_template_seed(seed: TemplateSeed) -> TemplateSeedValidation:
    findings: list[str] = []
    if not seed.template_id:
        findings.append("missing_template_id")
    if not seed.version:
        findings.append("missing_template_version")
    required_layers = {"route_scaffold", "reusable_branch_seed", "operator_guide", "flowguard_self_model"}
    missing_layers = sorted(required_layers - set(seed.layers))
    if missing_layers:
        findings.append("missing_layers:" + ",".join(missing_layers))
    if not seed.route_ids:
        findings.append("missing_route_ids")
    if not seed.predicates:
        findings.append("missing_exact_applicability_predicate")
    if not seed.protected_error_classes:
        findings.append("missing_protected_error_classes")
    if not seed.required_states:
        findings.append("missing_required_states")
    if not seed.required_side_effects:
        findings.append("missing_required_side_effects")
    if not seed.completion_evidence:
        findings.append("missing_completion_evidence")
    if not seed.positive_cases:
        findings.append("missing_positive_cases")
    if not seed.known_bad_cases:
        findings.append("missing_known_bad_cases")
    if not seed.false_friend_cases:
        findings.append("missing_false_friend_cases")
    if not seed.target_fields:
        findings.append("missing_target_fields")
    if seed.non_applicable_disposition != "proved_or_blocked":
        findings.append("invalid_non_applicable_disposition")
    if not seed.source_proof_refs:
        findings.append("missing_source_proof_refs")
    if seed.privacy_disposition not in TEMPLATE_SEED_PRIVACY_DISPOSITIONS:
        findings.append("invalid_privacy_disposition")
    if seed.privacy_disposition != "portable_public":
        findings.append("private_seed_not_promotable")
    if _seed_contains_private_value(seed.layers) or any(
        _seed_contains_private_value(item) for item in seed.source_proof_refs
    ):
        findings.append("private_provenance_not_allowed")
    if any(
        _seed_contains_self_owner_identifier(item)
        for item in (seed.template_id, *seed.route_ids, *seed.target_fields, *seed.source_proof_refs)
    ):
        findings.append("self_owner_id_not_allowed")
    if seed.promotion_status not in TEMPLATE_SEED_PROMOTION_STATUSES:
        findings.append("invalid_promotion_status")
    if seed.closure_disposition not in TEMPLATE_SEED_CLOSURE_DISPOSITIONS:
        findings.append("invalid_closure_disposition")
    if seed.closure_disposition != "pending" and not seed.closure_proof_ref:
        findings.append("missing_closure_proof")
    for index, predicate in enumerate(seed.predicates):
        findings.extend(_predicate_findings(predicate, seed.template_id or "seed", index))
    return TemplateSeedValidation("pass" if not findings else "blocked", tuple(sorted(set(findings))))


def select_template_seeds(
    seeds: Sequence[TemplateSeed],
    context: Mapping[str, Any],
) -> TemplateSeedSelection:
    valid: list[TemplateSeed] = []
    findings: list[str] = []
    for seed in seeds:
        validation = validate_template_seed(seed)
        if not validation.ok:
            findings.extend(f"invalid_seed:{seed.template_id}:{finding}" for finding in validation.findings)
            continue
        if seed.promotion_status != "promoted":
            continue
        if seed.closure_disposition != "pending":
            continue
        if all(_predicate_matches(predicate, context) for predicate in seed.predicates):
            valid.append(seed)
    matched_ids = tuple(sorted(seed.template_id for seed in valid))
    if len(valid) == 1:
        return TemplateSeedSelection("selected", matched_ids, matched_ids, tuple(sorted(set(findings))))
    if not valid:
        findings.append("seed_no_exact_match")
        return TemplateSeedSelection("blocked", (), (), tuple(sorted(set(findings))))
    findings.append("seed_multiple_exact_matches:" + ",".join(matched_ids))
    return TemplateSeedSelection("blocked", matched_ids, (), tuple(sorted(set(findings))))


def close_template_seed(
    seed: TemplateSeed,
    *,
    disposition: str,
    proof_ref: str = "",
) -> TemplateSeedValidation:
    if disposition not in TEMPLATE_SEED_CLOSURE_DISPOSITIONS or disposition == "pending":
        return TemplateSeedValidation("blocked", ("invalid_or_pending_closure",))
    if not str(proof_ref).strip():
        return TemplateSeedValidation("blocked", ("missing_closure_proof",))
    return validate_template_seed(replace(seed, closure_disposition=disposition, closure_proof_ref=proof_ref))


def builtin_template_seeds() -> tuple[TemplateSeed, ...]:
    """Return portable promoted branch seeds distilled from public checks.

    These seeds contain no target model IDs, target paths or private provenance.
    They are branch scaffolds only; selection still leaves the
    target-owned closure disposition pending.
    """

    common_layers = {
        "route_scaffold": {"kind": "target-owned route scaffold"},
        "reusable_branch_seed": {"kind": "public proven branch pattern"},
        "operator_guide": {"kind": "replace with current target facts"},
        "flowguard_self_model": {"claim_boundary": "seed guidance is not target evidence"},
    }
    return (
        TemplateSeed(
            template_id="public-model-mesh-branch",
            version="1",
            route_ids=("model_mesh_maintenance",),
            layers=common_layers,
            predicates=(HardPredicate("route_id", "equals", "model_mesh_maintenance"),),
            protected_error_classes=(
                "mesh_missing_parent_partition",
                "mesh_overlapping_siblings",
                "mesh_stale_child_evidence",
            ),
            required_states=("partition_declared", "child_reattached", "closure_current"),
            required_side_effects=("child_owner_join", "parent_join", "terminal_record"),
            completion_evidence=("target_mesh_record", "target_child_results"),
            positive_cases=("complete_parent_child_partition",),
            known_bad_cases=("missing_partition", "overlapping_siblings", "stale_child_result"),
            false_friend_cases=("model_count_without_topology",),
            target_fields=("parent_partition", "child_owner", "reattachment_boundary"),
            non_applicable_disposition="proved_or_blocked",
            source_proof_refs=("tests:test_hierarchical_mesh",),
            promotion_status="promoted",
            closure_disposition="pending",
        ),
        TemplateSeed(
            template_id="public-contract-exhaustion-branch",
            version="1",
            route_ids=("contract_exhaustion_mesh",),
            layers=common_layers,
            predicates=(HardPredicate("route_id", "equals", "contract_exhaustion_mesh"),),
            protected_error_classes=(
                "exhaustion_missing_denominator",
                "exhaustion_missing_oracle",
                "exhaustion_duplicate_case",
            ),
            required_states=("finite_universe_declared", "cases_materialized", "oracle_closed"),
            required_side_effects=("stable_case_ids", "shard_owner_records"),
            completion_evidence=("contract_exhaustion_record", "test_mesh_record"),
            positive_cases=("finite_dimension_with_oracle",),
            known_bad_cases=("missing_denominator", "missing_oracle", "duplicate_case_id", "hidden_reject_case"),
            false_friend_cases=("observed_cases_without_universe",),
            target_fields=("dimension_universe", "oracle", "case_id", "shard_owner"),
            non_applicable_disposition="proved_or_blocked",
            source_proof_refs=("tests:test_contract_exhaustion", "tests:test_behavior_commitment_contract_exhaustion"),
            promotion_status="promoted",
            closure_disposition="pending",
        ),
        TemplateSeed(
            template_id="public-reverse-surface-closure-branch",
            version="1",
            route_ids=("reverse_surface_closure",),
            layers=common_layers,
            predicates=(HardPredicate("route_id", "equals", "reverse_surface_closure"),),
            protected_error_classes=(
                "reverse_surface_unmapped",
                "reverse_surface_one_way",
                "reverse_surface_ui_action_gap",
            ),
            required_states=("independent_denominator_declared", "two_way_join_current", "graduation_closed"),
            required_side_effects=("owner_test_result_join", "ui_action_join", "authority_join"),
            completion_evidence=("reverse_surface_audit_record", "current_owner_authority"),
            positive_cases=("exact_bidirectional_surface_map",),
            known_bad_cases=("unmapped_surface", "orphan_obligation", "one_way_join", "ui_action_gap"),
            false_friend_cases=("name_match_without_bidirectional_join",),
            target_fields=("implementation_denominator", "model_obligation_denominator", "dynamic_boundary"),
            non_applicable_disposition="proved_or_blocked",
            source_proof_refs=("tests:test_public_behavior_surface_audit", "tests:test_reverse_surface_current_closure"),
            promotion_status="promoted",
            closure_disposition="pending",
        ),
    )


def _predicate_findings(predicate: HardPredicate, template_id: str, index: int) -> tuple[str, ...]:
    prefix = f"predicate:{template_id}:{index}"
    findings: list[str] = []
    if not predicate.key:
        findings.append(f"{prefix}:missing_key")
    if predicate.operator not in PREDICATE_OPERATORS:
        findings.append(f"{prefix}:unsupported_operator:{predicate.operator or '(empty)'}")
        return tuple(findings)
    expected = predicate.expected
    if predicate.operator == "exists" and not isinstance(expected, bool):
        findings.append(f"{prefix}:exists_expected_must_be_boolean")
    elif predicate.operator in ("one_of", "contains_all"):
        if not isinstance(expected, tuple) or not expected:
            findings.append(f"{prefix}:{predicate.operator}_expected_must_be_nonempty_array")
        elif any(isinstance(item, (Mapping, tuple)) for item in expected):
            findings.append(f"{prefix}:{predicate.operator}_items_must_be_scalars")
    elif predicate.operator == "contains" and isinstance(expected, (Mapping, tuple)):
        findings.append(f"{prefix}:contains_expected_must_be_scalar")
    return tuple(findings)


def _predicate_matches(predicate: HardPredicate, context: Mapping[str, Any]) -> bool:
    present = predicate.key in context
    if predicate.operator == "exists":
        return present is predicate.expected
    if not present:
        return False
    candidate = context[predicate.key]
    if predicate.operator == "equals":
        return _json_equal(candidate, predicate.expected)
    if predicate.operator == "one_of":
        return any(_json_equal(candidate, expected) for expected in predicate.expected)
    if predicate.operator == "contains":
        if isinstance(candidate, str):
            return isinstance(predicate.expected, str) and predicate.expected in candidate
        if isinstance(candidate, Mapping):
            return predicate.expected in candidate
        if isinstance(candidate, tuple):
            return any(_json_equal(predicate.expected, item) for item in candidate)
        return False
    if predicate.operator == "contains_all":
        if isinstance(candidate, str):
            return all(isinstance(item, str) and item in candidate for item in predicate.expected)
        if isinstance(candidate, Mapping):
            return all(item in candidate for item in predicate.expected)
        if isinstance(candidate, tuple):
            return all(
                any(_json_equal(expected, item) for item in candidate)
                for expected in predicate.expected
            )
        return False
    return False


__all__ = ['HardPredicate', 'PREDICATE_OPERATORS', 'TEMPLATE_SEED_CLOSURE_DISPOSITIONS', 'TEMPLATE_SEED_PRIVACY_DISPOSITIONS', 'TEMPLATE_SEED_PROMOTION_STATUSES', 'TEMPLATE_SEED_SCHEMA', 'TemplateSeed', 'TemplateSeedSelection', 'TemplateSeedValidation', 'close_template_seed', 'builtin_template_seeds', 'select_template_seeds', 'validate_template_seed']
