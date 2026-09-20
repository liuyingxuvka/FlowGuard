"""Explicit lifecycle and modeling-mode selection for FlowGuard entries.

``execution_profile`` controls how much of the current project is executed;
``modeling_mode`` describes the semantic modeling boundary.  They are separate
identities on purpose.  The user-facing lifecycle is deliberately smaller than
the internal execution-depth implementation: callers choose only ``read``,
``change``, or ``release``.  Specialist/domain analyzer routes never silently
turn one lifecycle into another.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import tomllib
from typing import Any, Mapping, Sequence


EXECUTION_PROFILE_LIGHT = "light"
EXECUTION_PROFILE_AFFECTED = "affected"
EXECUTION_PROFILE_FULL = "full"
EXECUTION_PROFILES = (
    EXECUTION_PROFILE_LIGHT,
    EXECUTION_PROFILE_AFFECTED,
    EXECUTION_PROFILE_FULL,
)

# Lifecycle is the only public selector.  Execution profiles remain internal
# implementation identities so existing owner code can still distinguish the
# amount of work behind each lifecycle without exposing those names as a
# caller-facing choice.
LIFECYCLE_READ = "read"
LIFECYCLE_CHANGE = "change"
LIFECYCLE_RELEASE = "release"
LIFECYCLES = (
    LIFECYCLE_READ,
    LIFECYCLE_CHANGE,
    LIFECYCLE_RELEASE,
)

MODELING_MODE_READ_ONLY_AUDIT = "read_only_audit"
MODELING_MODE_MODEL_FIRST_CHANGE = "model_first_change"
MODELING_MODE_MODEL_MAINTENANCE = "model_maintenance"
MODELING_MODE_LAYERED_BOUNDARY_PROOF = "layered_boundary_proof"
MODELING_MODES = (
    MODELING_MODE_READ_ONLY_AUDIT,
    MODELING_MODE_MODEL_FIRST_CHANGE,
    MODELING_MODE_MODEL_MAINTENANCE,
    MODELING_MODE_LAYERED_BOUNDARY_PROOF,
)

# Operation facts are deliberately separate from the three execution profiles.
# A route (or a caller's prose label) is not permission to execute a deeper
# validation profile.  These values are intentionally small and typed so that
# callers with a structured task record do not have to rely on keyword
# inference.
OPERATION_KIND_READ_ONLY = "read_only"
OPERATION_KIND_CHANGE = "change"
OPERATION_KIND_QUALIFICATION = "qualification"
OPERATION_KINDS = (
    OPERATION_KIND_READ_ONLY,
    OPERATION_KIND_CHANGE,
    OPERATION_KIND_QUALIFICATION,
)


_PROFILE_FOR_OPERATION_KIND = {
    OPERATION_KIND_READ_ONLY: EXECUTION_PROFILE_LIGHT,
    OPERATION_KIND_CHANGE: EXECUTION_PROFILE_AFFECTED,
    OPERATION_KIND_QUALIFICATION: EXECUTION_PROFILE_FULL,
}

_PROFILE_FOR_LIFECYCLE = {
    LIFECYCLE_READ: EXECUTION_PROFILE_LIGHT,
    LIFECYCLE_CHANGE: EXECUTION_PROFILE_AFFECTED,
    LIFECYCLE_RELEASE: EXECUTION_PROFILE_FULL,
}
_LIFECYCLE_FOR_PROFILE = {
    profile: lifecycle for lifecycle, profile in _PROFILE_FOR_LIFECYCLE.items()
}
_LIFECYCLE_FOR_OPERATION_KIND = {
    OPERATION_KIND_READ_ONLY: LIFECYCLE_READ,
    OPERATION_KIND_CHANGE: LIFECYCLE_CHANGE,
    OPERATION_KIND_QUALIFICATION: LIFECYCLE_RELEASE,
}

_DEFAULT_MODELING_MODE = {
    EXECUTION_PROFILE_LIGHT: MODELING_MODE_READ_ONLY_AUDIT,
    EXECUTION_PROFILE_AFFECTED: MODELING_MODE_MODEL_FIRST_CHANGE,
    EXECUTION_PROFILE_FULL: MODELING_MODE_LAYERED_BOUNDARY_PROOF,
}
_CLAIM_BOUNDARY = {
    EXECUTION_PROFILE_LIGHT: (
        "Light proves only read-only shape/currentness and compact route data; "
        "it does not execute native owners or make a whole-system claim."
    ),
    EXECUTION_PROFILE_AFFECTED: (
        "Affected proves only the exact current changed-path closure, its explicit "
        "owners, and their terminal receipts; it cannot support release/full claims."
    ),
    EXECUTION_PROFILE_FULL: (
        "Full proves the complete frozen owner DAG and whole-system terminal result "
        "only after all governed inputs and projections are frozen."
    ),
}


class ExecutionProfileError(ValueError):
    """Raised when a profile/mode decision is malformed or inadmissible."""


DEFAULT_VALIDATION_EXECUTION_POLICY = {
    "invocation_timeout_seconds": 7200.0,
    "observation_timeout_seconds": 120.0,
    "collection_timeout_seconds": 240.0,
    "pytest_shard_timeout_seconds": 2400.0,
    "profile_timeout_seconds": {
        "fast": 30.0,
        "focused": 120.0,
        "full": 900.0,
    },
}
DEFAULT_OWNER_TIMEOUT_SECONDS = {
    "skill_native_checks": 3600.0,
    "model_regressions_full": 3600.0,
    "self_maintenance_review": 1800.0,
    "pytest": 3600.0,
}


class ValidationExecutionPolicyError(ExecutionProfileError):
    """Raised when the current bounded execution-policy table is invalid."""


@dataclass(frozen=True)
class ValidationExecutionPolicy:
    """Finite supervisor budgets kept outside functional owner identity.

    This object is execution metadata only.  It deliberately does not enter
    a validation-owner contract hash or model functional projection.  A
    changed cap can therefore affect whether an unfinished owner is run, but
    cannot turn an already passed functional receipt stale.
    """

    schema: str = "flowguard.resource_policy.v1"
    invocation_timeout_seconds: float = DEFAULT_VALIDATION_EXECUTION_POLICY[
        "invocation_timeout_seconds"
    ]
    observation_timeout_seconds: float = DEFAULT_VALIDATION_EXECUTION_POLICY[
        "observation_timeout_seconds"
    ]
    collection_timeout_seconds: float = DEFAULT_VALIDATION_EXECUTION_POLICY[
        "collection_timeout_seconds"
    ]
    owner_timeout_seconds: Mapping[str, float] = ()
    pytest_shard_timeout_seconds: float = DEFAULT_VALIDATION_EXECUTION_POLICY[
        "pytest_shard_timeout_seconds"
    ]
    profile_timeout_seconds: Mapping[str, float] = ()

    def __post_init__(self) -> None:
        if self.schema != "flowguard.resource_policy.v1":
            raise ValidationExecutionPolicyError(
                "resource policy schema must be flowguard.resource_policy.v1"
            )
        values = (
            "invocation_timeout_seconds",
            "observation_timeout_seconds",
            "collection_timeout_seconds",
            "pytest_shard_timeout_seconds",
        )
        for field_name in values:
            value = float(getattr(self, field_name))
            if not math.isfinite(value) or value <= 0:
                raise ValidationExecutionPolicyError(
                    f"{field_name} must be finite and positive"
                )
            object.__setattr__(self, field_name, value)
        raw_owner = self.owner_timeout_seconds
        if not isinstance(raw_owner, Mapping):
            if raw_owner in ((), None):
                raw_owner = {}
            else:
                raise ValidationExecutionPolicyError(
                    "owner_timeout_seconds must be a mapping"
                )
        normalized: dict[str, float] = {}
        for owner_id, raw_value in raw_owner.items():
            key = str(owner_id).strip()
            if not key:
                raise ValidationExecutionPolicyError(
                    "owner_timeout_seconds keys must be non-empty"
                )
            value = float(raw_value)
            if not math.isfinite(value) or value <= 0:
                raise ValidationExecutionPolicyError(
                    f"owner_timeout_seconds[{key!r}] must be finite and positive"
                )
            normalized[key] = value
        object.__setattr__(self, "owner_timeout_seconds", dict(sorted(normalized.items())))
        raw_profiles = self.profile_timeout_seconds
        if not isinstance(raw_profiles, Mapping):
            if raw_profiles in ((), None):
                raw_profiles = DEFAULT_VALIDATION_EXECUTION_POLICY[
                    "profile_timeout_seconds"
                ]
            else:
                raise ValidationExecutionPolicyError(
                    "profile_timeout_seconds must be a mapping"
                )
        normalized_profiles: dict[str, float] = {}
        for profile_id in ("fast", "focused", "full"):
            value = float(raw_profiles.get(profile_id, DEFAULT_VALIDATION_EXECUTION_POLICY[
                "profile_timeout_seconds"
            ][profile_id]))
            if not math.isfinite(value) or value <= 0:
                raise ValidationExecutionPolicyError(
                    f"profile_timeout_seconds[{profile_id!r}] must be finite and positive"
                )
            normalized_profiles[profile_id] = value
        unknown_profiles = sorted(set(raw_profiles) - set(normalized_profiles))
        if unknown_profiles:
            raise ValidationExecutionPolicyError(
                "profile_timeout_seconds keys are unsupported: "
                + ", ".join(unknown_profiles)
            )
        object.__setattr__(self, "profile_timeout_seconds", normalized_profiles)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "ValidationExecutionPolicy":
        """Parse exactly the current policy table; unknown fields fail closed."""

        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise ValidationExecutionPolicyError("flowguard_execution must be a table")
        allowed = {
            "schema",
            "invocation_timeout_seconds",
            "observation_timeout_seconds",
            "collection_timeout_seconds",
            "owner_timeout_seconds",
            "pytest_shard_timeout_seconds",
            "profile_timeout_seconds",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValidationExecutionPolicyError(
                "unknown resource policy fields: " + ", ".join(unknown)
            )
        defaults = DEFAULT_VALIDATION_EXECUTION_POLICY
        return cls(
            schema=str(value.get("schema", "flowguard.resource_policy.v1")),
            invocation_timeout_seconds=float(
                value.get("invocation_timeout_seconds", defaults["invocation_timeout_seconds"])
            ),
            observation_timeout_seconds=float(
                value.get("observation_timeout_seconds", defaults["observation_timeout_seconds"])
            ),
            collection_timeout_seconds=float(
                value.get("collection_timeout_seconds", defaults["collection_timeout_seconds"])
            ),
            owner_timeout_seconds=value.get("owner_timeout_seconds", {}),
            pytest_shard_timeout_seconds=float(
                value.get("pytest_shard_timeout_seconds", defaults["pytest_shard_timeout_seconds"])
            ),
            profile_timeout_seconds=value.get(
                "profile_timeout_seconds", defaults["profile_timeout_seconds"]
            ),
        )

    @classmethod
    def from_project(cls, root: str | Path = ".") -> "ValidationExecutionPolicy":
        """Load the sole current policy table from ``.flowguard/project.toml``."""

        path = Path(root).resolve() / ".flowguard" / "project.toml"
        if not path.is_file():
            return cls()
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise ValidationExecutionPolicyError(
                f"cannot read current execution policy manifest: {path}"
            ) from exc
        return cls.from_mapping(payload.get("flowguard_execution"))

    def owner_timeout(self, owner_id: str) -> float:
        """Return the exact owner cap or the bounded current default."""

        key = str(owner_id).strip()
        return float(
            self.owner_timeout_seconds.get(
                key,
                DEFAULT_OWNER_TIMEOUT_SECONDS.get(key, 900.0),
            )
        )

    def profile_timeout(self, profile_id: str) -> float:
        """Return the finite operational budget for one execution profile."""

        key = str(profile_id).strip()
        if key not in self.profile_timeout_seconds:
            raise ValidationExecutionPolicyError(
                f"unknown execution profile: {profile_id}"
            )
        return float(self.profile_timeout_seconds[key])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "invocation_timeout_seconds": self.invocation_timeout_seconds,
            "observation_timeout_seconds": self.observation_timeout_seconds,
            "collection_timeout_seconds": self.collection_timeout_seconds,
            "owner_timeout_seconds": dict(self.owner_timeout_seconds),
            "pytest_shard_timeout_seconds": self.pytest_shard_timeout_seconds,
            "profile_timeout_seconds": dict(self.profile_timeout_seconds),
        }


@dataclass(frozen=True)
class ExecutionProfileDecision:
    execution_profile: str
    modeling_mode: str
    claim_boundary: str
    selection_reason: str
    closed_obligations: tuple[str, ...] = ()
    not_run_obligations: tuple[str, ...] = ()
    escalation_triggers: tuple[str, ...] = ()
    admitted: bool = True
    status: str = "pass"

    def __post_init__(self) -> None:
        if self.execution_profile not in EXECUTION_PROFILES:
            raise ExecutionProfileError(
                f"execution_profile must be one of {EXECUTION_PROFILES}"
            )
        if self.modeling_mode not in MODELING_MODES:
            raise ExecutionProfileError(
                f"modeling_mode must be one of {MODELING_MODES}"
            )
        if self.status not in {"pass", "blocked"}:
            raise ExecutionProfileError("execution profile status must be pass or blocked")
        for field_name in (
            "closed_obligations",
            "not_run_obligations",
            "escalation_triggers",
        ):
            values = tuple(sorted({str(item).strip() for item in getattr(self, field_name) if str(item).strip()}))
            object.__setattr__(self, field_name, values)
        object.__setattr__(self, "claim_boundary", str(self.claim_boundary).strip())
        object.__setattr__(self, "selection_reason", str(self.selection_reason).strip())
        if not self.claim_boundary or not self.selection_reason:
            raise ExecutionProfileError("profile decision requires a claim boundary and selection reason")
        if self.status == "pass" and not self.admitted:
            raise ExecutionProfileError("a passing profile decision must be admitted")
        if self.status == "blocked" and self.admitted:
            raise ExecutionProfileError("a blocked profile decision cannot be admitted")

    @property
    def ok(self) -> bool:
        return self.status == "pass" and self.admitted and not self.escalation_triggers

    @property
    def lifecycle(self) -> str:
        """Return the stable public lifecycle for this internal profile."""

        return _LIFECYCLE_FOR_PROFILE[self.execution_profile]

    def to_dict(self) -> dict[str, Any]:
        return {
            "lifecycle": self.lifecycle,
            "execution_profile": self.execution_profile,
            "modeling_mode": self.modeling_mode,
            "claim_boundary": self.claim_boundary,
            "selection_reason": self.selection_reason,
            "closed_obligations": list(self.closed_obligations),
            "not_run_obligations": list(self.not_run_obligations),
            "escalation_triggers": list(self.escalation_triggers),
            "admitted": self.admitted,
            "status": self.status,
            "ok": self.ok,
        }


def select_execution_profile(
    lifecycle: str | None = None,
    *,
    operation_kind: str | None = None,
    route_kind: str = "",
    modeling_mode: str | None = None,
    changed_paths: Sequence[str] = (),
    governed_writes_frozen: bool = False,
    projections_frozen: bool = False,
    openspec_frozen: bool = False,
    owner_dag_frozen: bool = False,
    reverse_input_frozen: bool = False,
    closed_obligations: Sequence[str] = (),
    not_run_obligations: Sequence[str] = (),
) -> ExecutionProfileDecision:
    """Select one internal profile from the explicit public lifecycle.

    ``lifecycle`` accepts exactly ``read``, ``change``, or ``release``.
    Internal ``light``, ``affected``, and ``full`` profile names are rejected
    at this boundary, and omitting both lifecycle and the typed operation fact
    is rejected rather than falling back to a read/light profile.  The typed
    ``operation_kind`` is retained for domain-owned callers that already carry
    that fact; it is not a second public lifecycle vocabulary.
    """

    changed = tuple(sorted({str(item).strip().replace("\\", "/") for item in changed_paths if str(item).strip()}))
    if operation_kind is not None:
        normalized_kind = str(operation_kind).strip().lower()
        if normalized_kind not in OPERATION_KINDS:
            raise ExecutionProfileError(
                f"operation_kind must be one of {OPERATION_KINDS}"
            )
        inferred_kind: str | None = normalized_kind
        operation_reason = f"typed operation_kind={normalized_kind}"
    else:
        inferred_kind = None
        operation_reason = None

    explicit_lifecycle = str(lifecycle).strip().lower() if lifecycle is not None else ""
    if explicit_lifecycle in EXECUTION_PROFILES:
        raise ExecutionProfileError(
            "execution profile names are internal; lifecycle must be one of "
            f"{LIFECYCLES}"
        )
    if explicit_lifecycle and explicit_lifecycle not in LIFECYCLES:
        raise ExecutionProfileError(f"lifecycle must be one of {LIFECYCLES}")

    if explicit_lifecycle:
        selected_lifecycle = explicit_lifecycle
        if inferred_kind is not None:
            expected_lifecycle = _LIFECYCLE_FOR_OPERATION_KIND[inferred_kind]
            if selected_lifecycle != expected_lifecycle:
                raise ExecutionProfileError(
                    "lifecycle conflicts with operation_kind: "
                    f"{selected_lifecycle!r} vs {expected_lifecycle!r}"
                )
        selection_reason = f"explicit lifecycle={selected_lifecycle}"
        if operation_reason:
            selection_reason += f"; {operation_reason}"
    elif inferred_kind is not None:
        selected_lifecycle = _LIFECYCLE_FOR_OPERATION_KIND[inferred_kind]
        selection_reason = (
            f"typed operation_kind={inferred_kind}; selected lifecycle={selected_lifecycle}"
        )
    else:
        raise ExecutionProfileError(
            "lifecycle is required; no light/affected/full default fallback is available"
        )

    profile = _PROFILE_FOR_LIFECYCLE[selected_lifecycle]
    mode = str(modeling_mode).strip() if modeling_mode else _DEFAULT_MODELING_MODE[profile]
    if mode not in MODELING_MODES:
        raise ExecutionProfileError(f"modeling_mode must be one of {MODELING_MODES}")

    triggers: list[str] = []
    if inferred_kind is not None:
        expected_profile = _PROFILE_FOR_OPERATION_KIND[inferred_kind]
        if profile != expected_profile:
            if inferred_kind == OPERATION_KIND_READ_ONLY:
                trigger = f"{profile}_profile_read_only_intent_conflict"
            elif inferred_kind == OPERATION_KIND_CHANGE:
                trigger = (
                    "read_only_profile_write_intent_conflict"
                    if profile == EXECUTION_PROFILE_LIGHT
                    else f"{profile}_profile_change_intent_conflict"
                )
            else:
                trigger = (
                    "read_only_profile_qualification_intent_conflict"
                    if profile == EXECUTION_PROFILE_LIGHT
                    else f"{profile}_profile_qualification_intent_conflict"
                )
            triggers.append(trigger)
    if profile == EXECUTION_PROFILE_AFFECTED and not changed:
        triggers.append("affected_changed_paths_required")
    if profile == EXECUTION_PROFILE_FULL:
        if not governed_writes_frozen:
            triggers.append("governed_writes_not_frozen")
        if not projections_frozen:
            triggers.append("projections_not_frozen")
        if not openspec_frozen:
            triggers.append("openspec_not_frozen")
        if not owner_dag_frozen:
            triggers.append("owner_dag_not_frozen")
        if not reverse_input_frozen:
            triggers.append("reverse_input_not_frozen")
    # A specialist route supplies semantic ownership, not execution depth.
    if route_kind and route_kind not in {"release", "integration", "whole_system"}:
        selection_reason += "; specialist route does not auto-upgrade execution profile"

    not_run = tuple(sorted({str(item).strip() for item in not_run_obligations if str(item).strip()}))
    if not_run and profile == EXECUTION_PROFILE_FULL:
        triggers.append("full_not_run_obligations_present")
    status = "blocked" if triggers else "pass"
    return ExecutionProfileDecision(
        execution_profile=profile,
        modeling_mode=mode,
        claim_boundary=_CLAIM_BOUNDARY[profile],
        selection_reason=selection_reason,
        closed_obligations=tuple(closed_obligations),
        not_run_obligations=not_run,
        escalation_triggers=tuple(sorted(set(triggers))),
        admitted=not triggers,
        status=status,
    )


def validate_execution_profile_decision(value: Mapping[str, Any]) -> ExecutionProfileDecision:
    """Validate a machine profile projection without trusting ``ok`` flags."""

    if not isinstance(value, Mapping):
        raise ExecutionProfileError("execution profile decision must be an object")
    required = {
        "lifecycle",
        "execution_profile",
        "modeling_mode",
        "claim_boundary",
        "selection_reason",
        "closed_obligations",
        "not_run_obligations",
        "escalation_triggers",
        "admitted",
        "status",
        "ok",
    }
    if set(value) != required:
        raise ExecutionProfileError(
            "execution profile decision fields are not current: "
            + repr(sorted(set(value) ^ required))
        )
    decision = ExecutionProfileDecision(
        execution_profile=str(value["execution_profile"]),
        modeling_mode=str(value["modeling_mode"]),
        claim_boundary=str(value["claim_boundary"]),
        selection_reason=str(value["selection_reason"]),
        closed_obligations=tuple(value["closed_obligations"]),
        not_run_obligations=tuple(value["not_run_obligations"]),
        escalation_triggers=tuple(value["escalation_triggers"]),
        admitted=bool(value["admitted"]),
        status=str(value["status"]),
    )
    if str(value["lifecycle"]) != decision.lifecycle:
        raise ExecutionProfileError("lifecycle is derived from the internal execution profile")
    if bool(value["ok"]) != decision.ok:
        raise ExecutionProfileError("profile ok is derived and cannot be caller-authored")
    return decision


__all__ = [
    "EXECUTION_PROFILE_AFFECTED",
    "EXECUTION_PROFILE_FULL",
    "EXECUTION_PROFILE_LIGHT",
    "EXECUTION_PROFILES",
    "LIFECYCLE_CHANGE",
    "LIFECYCLE_READ",
    "LIFECYCLE_RELEASE",
    "LIFECYCLES",
    "OPERATION_KIND_CHANGE",
    "OPERATION_KIND_QUALIFICATION",
    "OPERATION_KIND_READ_ONLY",
    "OPERATION_KINDS",
    "MODELING_MODE_LAYERED_BOUNDARY_PROOF",
    "MODELING_MODE_MODEL_FIRST_CHANGE",
    "MODELING_MODE_MODEL_MAINTENANCE",
    "MODELING_MODE_READ_ONLY_AUDIT",
    "MODELING_MODES",
    "ExecutionProfileDecision",
    "ExecutionProfileError",
    "DEFAULT_VALIDATION_EXECUTION_POLICY",
    "ValidationExecutionPolicy",
    "ValidationExecutionPolicyError",
    "select_execution_profile",
    "validate_execution_profile_decision",
]
