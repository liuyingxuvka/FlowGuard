"""Roadmap-independent real software problem corpus structures."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


@dataclass(frozen=True)
class ProblemCase:
    """One real software workflow problem case.

    A problem case describes test intent from the software problem space. It
    intentionally does not record future phase ownership, current flowguard
    support, or roadmap mapping.
    """

    case_id: str
    title: str
    software_domain: str
    workflow_family: str
    software_structure: str
    operation_boundary: str
    actors: tuple[str, ...]
    external_inputs: tuple[str, ...]
    initial_state_shape: str
    state_transition_focus: str
    side_effects: tuple[str, ...]
    expected_behavior: str
    forbidden_behavior: tuple[str, ...]
    failure_mode: str
    evidence_to_check: tuple[str, ...]
    oracle_type: str
    case_kind: str
    importance: str
    non_goals: tuple[str, ...] = ()
    notes: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", str(self.case_id))
        object.__setattr__(self, "title", str(self.title))
        object.__setattr__(self, "software_domain", str(self.software_domain))
        object.__setattr__(self, "workflow_family", str(self.workflow_family))
        object.__setattr__(self, "software_structure", str(self.software_structure))
        object.__setattr__(self, "operation_boundary", str(self.operation_boundary))
        object.__setattr__(self, "actors", tuple(str(item) for item in self.actors))
        object.__setattr__(self, "external_inputs", tuple(str(item) for item in self.external_inputs))
        object.__setattr__(self, "initial_state_shape", str(self.initial_state_shape))
        object.__setattr__(self, "state_transition_focus", str(self.state_transition_focus))
        object.__setattr__(self, "side_effects", tuple(str(item) for item in self.side_effects))
        object.__setattr__(self, "expected_behavior", str(self.expected_behavior))
        object.__setattr__(
            self,
            "forbidden_behavior",
            tuple(str(item) for item in self.forbidden_behavior),
        )
        object.__setattr__(self, "failure_mode", str(self.failure_mode))
        object.__setattr__(
            self,
            "evidence_to_check",
            tuple(str(item) for item in self.evidence_to_check),
        )
        object.__setattr__(self, "oracle_type", str(self.oracle_type))
        object.__setattr__(self, "case_kind", str(self.case_kind))
        object.__setattr__(self, "importance", str(self.importance))
        object.__setattr__(self, "non_goals", tuple(str(item) for item in self.non_goals))
        object.__setattr__(self, "notes", str(self.notes))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        required_string_fields = (
            "case_id",
            "title",
            "software_domain",
            "workflow_family",
            "software_structure",
            "operation_boundary",
            "initial_state_shape",
            "state_transition_focus",
            "expected_behavior",
            "failure_mode",
            "oracle_type",
            "case_kind",
            "importance",
        )
        for field_name in required_string_fields:
            if not getattr(self, field_name).strip():
                errors.append(f"{self.case_id or '(missing id)'} missing {field_name}")

        required_tuple_fields = (
            "actors",
            "external_inputs",
            "side_effects",
            "evidence_to_check",
        )
        for field_name in required_tuple_fields:
            if not getattr(self, field_name):
                errors.append(f"{self.case_id} missing {field_name}")

        if not self.forbidden_behavior and not self.non_goals:
            errors.append(f"{self.case_id} needs forbidden_behavior or explicit non_goals")

        forbidden_roadmap_terms = (
            "phase_11",
            "phase_12",
            "phase_13",
            "phase_14",
            "phase_15",
            "phase 11",
            "phase 12",
            "phase 13",
            "phase 14",
            "phase 15",
            "roadmap",
            "future_owner",
            "target_phase",
            "implemented_by",
            "current_capability",
            "support_status",
        )
        searchable = " ".join(
            [
                self.notes,
                *(str(key) for key, _value in self.metadata),
                *(str(value) for _key, value in self.metadata),
            ]
        ).lower()
        for term in forbidden_roadmap_terms:
            if term in searchable:
                errors.append(f"{self.case_id} contains roadmap/capability mapping term: {term}")

        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "software_domain": self.software_domain,
            "workflow_family": self.workflow_family,
            "software_structure": self.software_structure,
            "operation_boundary": self.operation_boundary,
            "actors": list(self.actors),
            "external_inputs": list(self.external_inputs),
            "initial_state_shape": self.initial_state_shape,
            "state_transition_focus": self.state_transition_focus,
            "side_effects": list(self.side_effects),
            "expected_behavior": self.expected_behavior,
            "forbidden_behavior": list(self.forbidden_behavior),
            "failure_mode": self.failure_mode,
            "evidence_to_check": list(self.evidence_to_check),
            "oracle_type": self.oracle_type,
            "case_kind": self.case_kind,
            "importance": self.importance,
            "non_goals": list(self.non_goals),
            "notes": self.notes,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class ProblemCorpus:
    """A deterministic collection of real software problem cases."""

    cases: tuple[ProblemCase, ...]
    name: str = "real_software_problem_corpus"
    description: str = ""

    def __init__(
        self,
        cases: Iterable[ProblemCase],
        name: str = "real_software_problem_corpus",
        description: str = "",
    ) -> None:
        object.__setattr__(self, "cases", tuple(cases))
        object.__setattr__(self, "name", str(name))
        object.__setattr__(self, "description", str(description))

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        seen: set[str] = set()
        duplicates: set[str] = set()
        for case in self.cases:
            if case.case_id in seen:
                duplicates.add(case.case_id)
            seen.add(case.case_id)
            errors.extend(case.validate())
        for case_id in sorted(duplicates):
            errors.append(f"duplicate case_id: {case_id}")
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "cases": [case.to_dict() for case in self.cases],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


@dataclass(frozen=True)
class ProblemCorpusReport:
    """Quality report for a problem corpus."""

    ok: bool
    total_cases: int
    min_cases: int
    workflow_family_count: int
    failure_mode_count: int
    case_kind_counts: tuple[tuple[str, int], ...]
    workflow_family_counts: tuple[tuple[str, int], ...]
    failure_mode_counts: tuple[tuple[str, int], ...]
    oracle_type_counts: tuple[tuple[str, int], ...]
    software_domain_counts: tuple[tuple[str, int], ...]
    validation_errors: tuple[str, ...]
    case_source_counts: tuple[tuple[str, int], ...] = ()
    gap_focus_counts: tuple[tuple[str, int], ...] = ()
    pressure_focus_counts: tuple[tuple[str, int], ...] = ()
    count_semantics: str = "problem_intent_cases"
    execution_claim: str = "not_executable_tests"
    max_workflow_family_share: float = 0.0
    top_5_failure_mode_share: float = 0.0
    software_domain_count: int = 0
    max_software_domain_share: float = 0.0
    near_duplicate_group_max: int = 0
    expected_behavior_uniqueness: float = 0.0
    evidence_uniqueness: float = 0.0
    summary: str = ""

    def count_case_kind(self, case_kind: str) -> int:
        return int(dict(self.case_kind_counts).get(case_kind, 0))

    def count_workflow_family(self, workflow_family: str) -> int:
        return int(dict(self.workflow_family_counts).get(workflow_family, 0))

    def count_failure_mode(self, failure_mode: str) -> int:
        return int(dict(self.failure_mode_counts).get(failure_mode, 0))

    def count_oracle_type(self, oracle_type: str) -> int:
        return int(dict(self.oracle_type_counts).get(oracle_type, 0))

    def count_case_source(self, case_source: str) -> int:
        return int(dict(self.case_source_counts).get(case_source, 0))

    def count_gap_focus(self, gap_focus: str) -> int:
        return int(dict(self.gap_focus_counts).get(gap_focus, 0))

    def count_pressure_focus(self, pressure_focus: str) -> int:
        return int(dict(self.pressure_focus_counts).get(pressure_focus, 0))

    def format_text(self, max_errors: int = 10) -> str:
        lines = [
            "=== flowguard real software problem corpus ===",
            "",
            f"status: {'OK' if self.ok else 'INVALID'}",
            f"count_semantics: {self.count_semantics}",
            f"execution_claim: {self.execution_claim}",
            f"total_cases: {self.total_cases}",
            f"min_cases: {self.min_cases}",
            f"workflow_families: {self.workflow_family_count}",
            f"failure_modes: {self.failure_mode_count}",
            f"software_domains: {self.software_domain_count}",
            f"max_workflow_family_share: {self.max_workflow_family_share:.3f}",
            f"top_5_failure_mode_share: {self.top_5_failure_mode_share:.3f}",
            f"max_software_domain_share: {self.max_software_domain_share:.3f}",
            f"near_duplicate_group_max: {self.near_duplicate_group_max}",
            f"expected_behavior_uniqueness: {self.expected_behavior_uniqueness:.3f}",
            f"evidence_uniqueness: {self.evidence_uniqueness:.3f}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")

        lines.extend(["", "Case kinds:"])
        for name, count in self.case_kind_counts:
            lines.append(f"  - {name}: {count}")

        if self.case_source_counts:
            lines.extend(["", "Corpus sections:"])
            for name, count in self.case_source_counts:
                lines.append(f"  - {name}: {count}")

        if self.gap_focus_counts:
            lines.extend(["", "Gap focus areas:"])
            for name, count in self.gap_focus_counts:
                lines.append(f"  - {name}: {count}")

        if self.pressure_focus_counts:
            lines.extend(["", "Pressure focus areas:"])
            for name, count in self.pressure_focus_counts:
                lines.append(f"  - {name}: {count}")

        lines.extend(["", "Workflow families:"])
        for name, count in self.workflow_family_counts:
            lines.append(f"  - {name}: {count}")

        lines.extend(["", "Failure modes:"])
        for name, count in self.failure_mode_counts:
            lines.append(f"  - {name}: {count}")

        lines.extend(["", "Oracle types:"])
        for name, count in self.oracle_type_counts:
            lines.append(f"  - {name}: {count}")

        if self.validation_errors:
            lines.extend(["", "Validation errors:"])
            for error in self.validation_errors[:max_errors]:
                lines.append(f"  - {error}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "count_semantics": self.count_semantics,
            "execution_claim": self.execution_claim,
            "total_cases": self.total_cases,
            "min_cases": self.min_cases,
            "workflow_family_count": self.workflow_family_count,
            "failure_mode_count": self.failure_mode_count,
            "case_kind_counts": dict(self.case_kind_counts),
            "workflow_family_counts": dict(self.workflow_family_counts),
            "failure_mode_counts": dict(self.failure_mode_counts),
            "oracle_type_counts": dict(self.oracle_type_counts),
            "software_domain_counts": dict(self.software_domain_counts),
            "case_source_counts": dict(self.case_source_counts),
            "gap_focus_counts": dict(self.gap_focus_counts),
            "pressure_focus_counts": dict(self.pressure_focus_counts),
            "validation_errors": list(self.validation_errors),
            "max_workflow_family_share": self.max_workflow_family_share,
            "top_5_failure_mode_share": self.top_5_failure_mode_share,
            "software_domain_count": self.software_domain_count,
            "max_software_domain_share": self.max_software_domain_share,
            "near_duplicate_group_max": self.near_duplicate_group_max,
            "expected_behavior_uniqueness": self.expected_behavior_uniqueness,
            "evidence_uniqueness": self.evidence_uniqueness,
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def _sorted_counts(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    counts = Counter(values)
    return tuple(sorted(counts.items(), key=lambda item: item[0]))


def _metadata_value(case: ProblemCase, key: str, default: str = "") -> str:
    for item_key, value in case.metadata:
        if item_key == key:
            return str(value)
    return default


def build_problem_corpus_report(
    corpus: ProblemCorpus,
    *,
    min_cases: int = 1000,
    min_workflow_families: int = 20,
    min_failure_modes: int = 20,
    min_cases_per_workflow_family: int = 50,
    min_loop_or_stuck_cases: int = 100,
    min_invalid_initial_state_cases: int = 100,
    min_software_domains: int = 10,
    max_workflow_family_share: float = 0.12,
    max_top_5_failure_mode_share: float = 0.45,
    max_software_domain_share: float = 0.20,
    max_near_duplicate_group: int = 8,
    min_text_uniqueness: float = 0.70,
    summary: str = "",
) -> ProblemCorpusReport:
    """Validate and summarize a real software problem corpus."""

    cases = corpus.cases
    validation_errors = list(corpus.validate())
    workflow_family_counts = _sorted_counts(case.workflow_family for case in cases)
    failure_mode_counts = _sorted_counts(case.failure_mode for case in cases)
    case_kind_counts = _sorted_counts(case.case_kind for case in cases)
    oracle_type_counts = _sorted_counts(case.oracle_type for case in cases)
    software_domain_counts = _sorted_counts(case.software_domain for case in cases)
    case_source_counts = _sorted_counts(
        _metadata_value(case, "corpus_section", "unspecified") for case in cases
    )
    gap_focus_counts = _sorted_counts(
        focus
        for focus in (_metadata_value(case, "gap_focus_area") for case in cases)
        if focus
    )
    pressure_focus_counts = _sorted_counts(
        focus
        for focus in (_metadata_value(case, "pressure_focus_area") for case in cases)
        if focus
    )
    total = len(cases) or 1
    max_family_share_value = (
        max((count for _name, count in workflow_family_counts), default=0) / total
    )
    top_5_failure_mode_share_value = (
        sum(count for _name, count in sorted(failure_mode_counts, key=lambda item: item[1], reverse=True)[:5])
        / total
    )
    max_domain_share_value = (
        max((count for _name, count in software_domain_counts), default=0) / total
    )
    near_duplicate_groups = Counter(
        (
            case.workflow_family,
            case.failure_mode,
            case.case_kind,
            case.expected_behavior,
            case.forbidden_behavior,
        )
        for case in cases
    )
    near_duplicate_group_max_value = max(near_duplicate_groups.values(), default=0)
    expected_uniqueness_value = len({case.expected_behavior for case in cases}) / total
    evidence_uniqueness_value = len({case.evidence_to_check for case in cases}) / total

    family_count_dict = dict(workflow_family_counts)
    for family, count in workflow_family_counts:
        if count < min_cases_per_workflow_family:
            validation_errors.append(
                f"workflow family {family!r} has {count}, expected at least {min_cases_per_workflow_family}"
            )

    kind_count_dict = dict(case_kind_counts)
    positive = kind_count_dict.get("positive_correct_case", 0)
    negative = kind_count_dict.get("negative_broken_case", 0)
    loop_or_stuck = kind_count_dict.get("loop_or_stuck_case", 0)
    invalid_initial = kind_count_dict.get("invalid_initial_state_case", 0)
    if negative < positive:
        validation_errors.append(
            f"negative_broken_case count {negative} is less than positive_correct_case count {positive}"
        )
    if loop_or_stuck < min_loop_or_stuck_cases:
        validation_errors.append(
            f"loop_or_stuck_case count {loop_or_stuck} is less than {min_loop_or_stuck_cases}"
        )
    if invalid_initial < min_invalid_initial_state_cases:
        validation_errors.append(
            f"invalid_initial_state_case count {invalid_initial} is less than {min_invalid_initial_state_cases}"
        )
    if len(cases) < min_cases:
        validation_errors.append(f"case count {len(cases)} is less than {min_cases}")
    if len(workflow_family_counts) < min_workflow_families:
        validation_errors.append(
            f"workflow family count {len(workflow_family_counts)} is less than {min_workflow_families}"
        )
    if len(failure_mode_counts) < min_failure_modes:
        validation_errors.append(
            f"failure mode count {len(failure_mode_counts)} is less than {min_failure_modes}"
        )
    if len(software_domain_counts) < min_software_domains:
        validation_errors.append(
            f"software domain count {len(software_domain_counts)} is less than {min_software_domains}"
        )
    if max_family_share_value > max_workflow_family_share:
        validation_errors.append(
            f"max workflow family share {max_family_share_value:.3f} exceeds {max_workflow_family_share:.3f}"
        )
    if top_5_failure_mode_share_value > max_top_5_failure_mode_share:
        validation_errors.append(
            f"top 5 failure mode share {top_5_failure_mode_share_value:.3f} exceeds {max_top_5_failure_mode_share:.3f}"
        )
    if max_domain_share_value > max_software_domain_share:
        validation_errors.append(
            f"max software domain share {max_domain_share_value:.3f} exceeds {max_software_domain_share:.3f}"
        )
    if near_duplicate_group_max_value > max_near_duplicate_group:
        validation_errors.append(
            f"near duplicate group max {near_duplicate_group_max_value} exceeds {max_near_duplicate_group}"
        )
    if expected_uniqueness_value < min_text_uniqueness:
        validation_errors.append(
            f"expected behavior uniqueness {expected_uniqueness_value:.3f} is less than {min_text_uniqueness:.3f}"
        )
    if evidence_uniqueness_value < min_text_uniqueness:
        validation_errors.append(
            f"evidence uniqueness {evidence_uniqueness_value:.3f} is less than {min_text_uniqueness:.3f}"
        )

    return ProblemCorpusReport(
        ok=not validation_errors,
        total_cases=len(cases),
        min_cases=min_cases,
        workflow_family_count=len(workflow_family_counts),
        failure_mode_count=len(failure_mode_counts),
        case_kind_counts=case_kind_counts,
        workflow_family_counts=workflow_family_counts,
        failure_mode_counts=failure_mode_counts,
        oracle_type_counts=oracle_type_counts,
        software_domain_counts=software_domain_counts,
        case_source_counts=case_source_counts,
        gap_focus_counts=gap_focus_counts,
        pressure_focus_counts=pressure_focus_counts,
        validation_errors=tuple(validation_errors),
        max_workflow_family_share=max_family_share_value,
        top_5_failure_mode_share=top_5_failure_mode_share_value,
        software_domain_count=len(software_domain_counts),
        max_software_domain_share=max_domain_share_value,
        near_duplicate_group_max=near_duplicate_group_max_value,
        expected_behavior_uniqueness=expected_uniqueness_value,
        evidence_uniqueness=evidence_uniqueness_value,
        summary=summary,
    )


__all__ = [
    "ProblemCase",
    "ProblemCorpus",
    "ProblemCorpusReport",
    "build_problem_corpus_report",
]
