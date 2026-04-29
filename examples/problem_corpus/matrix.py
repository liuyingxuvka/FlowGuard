"""Deterministic real software problem corpus matrix."""

from __future__ import annotations

from flowguard.corpus import ProblemCase, ProblemCorpus, ProblemCorpusReport, build_problem_corpus_report

from .taxonomy import (
    CASE_KIND_QUOTAS,
    FAILURE_MODES,
    GAP_FOCUS_AREAS,
    IMPORTANCE_LEVELS,
    INPUT_PATTERNS,
    ORACLE_TYPES,
    PRESSURE_FOCUS_AREAS,
    STATE_PATTERNS,
    WORKFLOW_FAMILIES,
)


KIND_CODES = {
    "positive_correct_case": "POS",
    "negative_broken_case": "NEG",
    "boundary_edge_case": "EDG",
    "invalid_initial_state_case": "INV",
    "loop_or_stuck_case": "LOP",
}


GAP_KIND_SEQUENCE = (
    "negative_broken_case",
    "negative_broken_case",
    "boundary_edge_case",
    "invalid_initial_state_case",
    "loop_or_stuck_case",
    "positive_correct_case",
)


def _select(items: tuple[str, ...], index: int) -> str:
    return items[index % len(items)]


def _failure_mode_index(family_index: int, kind_index: int, item_index: int) -> int:
    return (family_index * 7 + kind_index * 11 + item_index * 3) % len(FAILURE_MODES)


def _input_pattern_index(family_index: int, kind_index: int, item_index: int) -> int:
    return (family_index * 5 + kind_index * 7 + item_index * 2) % len(INPUT_PATTERNS)


def _state_pattern_index(family_index: int, kind_index: int, item_index: int) -> int:
    return (family_index * 3 + kind_index * 13 + item_index * 5) % len(STATE_PATTERNS)


def _oracle_type_index(family_index: int, kind_index: int, item_index: int) -> int:
    return (family_index * 2 + kind_index * 5 + item_index * 7) % len(ORACLE_TYPES)


def _case_title(
    family_name: str,
    case_kind: str,
    failure_mode: str,
    input_pattern: str,
) -> str:
    readable_kind = case_kind.replace("_", " ")
    readable_failure = failure_mode.replace("_", " ")
    readable_input = input_pattern.replace("_", " ")
    return f"{family_name}: {readable_kind} for {readable_failure} under {readable_input}"


def _expected_behavior(
    family: dict[str, object],
    case_kind: str,
    failure_mode: str,
    input_pattern: str,
    state_pattern: str,
) -> str:
    boundary = str(family["boundary"])
    if case_kind == "positive_correct_case":
        return (
            f"{boundary} handles {input_pattern} from {state_pattern} without "
            f"triggering {failure_mode}; allowed state changes remain traceable."
        )
    if case_kind == "negative_broken_case":
        return (
            f"{boundary} exposes {failure_mode} when {input_pattern} reaches "
            f"{state_pattern}; the oracle should make the violation observable."
        )
    if case_kind == "boundary_edge_case":
        return (
            f"{boundary} treats boundary input {input_pattern} from {state_pattern} "
            f"deterministically and keeps downstream behavior consumable."
        )
    if case_kind == "invalid_initial_state_case":
        return (
            f"{boundary} rejects or reports invalid starting state {state_pattern} "
            f"before accepting side effects related to {failure_mode}."
        )
    return (
        f"{boundary} must not get stuck, loop indefinitely, or make success "
        f"unreachable when {failure_mode} appears after {input_pattern}."
    )


def _forbidden_behavior(
    family: dict[str, object],
    case_kind: str,
    failure_mode: str,
    state_pattern: str,
) -> tuple[str, ...]:
    side_effects = tuple(family["side_effects"])
    primary_side_effect = side_effects[0]
    if case_kind == "positive_correct_case":
        return (
            f"Silently produce {failure_mode} while reporting success.",
            f"Modify {primary_side_effect} without a traceable state transition.",
        )
    if case_kind == "negative_broken_case":
        return (
            f"Treat {failure_mode} as acceptable behavior.",
            f"Hide evidence of {failure_mode} through projection or normalization.",
        )
    if case_kind == "boundary_edge_case":
        return (
            f"Drop the boundary input or route it to an unhandled branch.",
            f"Emit an output that downstream consumers cannot process.",
        )
    if case_kind == "invalid_initial_state_case":
        return (
            f"Continue from invalid state {state_pattern} as if it were valid.",
            f"Create {primary_side_effect} before reporting the invalid state.",
        )
    return (
        "Remain in a non-terminal state with no useful outgoing transition.",
        "Reach a terminal state and then continue mutating workflow state.",
    )


def _evidence(
    family: dict[str, object],
    case_kind: str,
    failure_mode: str,
    input_pattern: str,
    state_pattern: str,
) -> tuple[str, ...]:
    side_effects = tuple(family["side_effects"])
    primary_side_effect = side_effects[0]
    secondary_side_effect = side_effects[-1]
    if case_kind == "positive_correct_case":
        return (
            f"Trace for {input_pattern} contains no forbidden {failure_mode} label.",
            f"{primary_side_effect} count stays within the expected bound.",
            f"Final state derived from {state_pattern} remains compatible downstream.",
        )
    if case_kind == "negative_broken_case":
        return (
            f"Counterexample trace identifies {failure_mode}.",
            f"{primary_side_effect} or {secondary_side_effect} shows the bad side effect.",
            f"Observed state differs from the expected abstract transition.",
        )
    if case_kind == "boundary_edge_case":
        return (
            f"Boundary input {input_pattern} is consumed by a named branch.",
            "No exception, dead branch, or non-consumable output is produced.",
            f"State focus {state_pattern} is preserved or updated intentionally.",
        )
    if case_kind == "invalid_initial_state_case":
        return (
            f"Initial state predicate flags {state_pattern}.",
            f"No new {primary_side_effect} is created after invalid state detection.",
            f"The report names {failure_mode} or the invalid state reason.",
        )
    return (
        "Reachable graph records the loop, stuck state, or unreachable success.",
        f"Trace evidence names {failure_mode}.",
        "Terminal semantics remain explicit in the report.",
    )


def _state_transition_focus(
    family: dict[str, object],
    failure_mode: str,
    state_pattern: str,
) -> str:
    return (
        f"Track {state_pattern} across {family['boundary']} and verify that "
        f"state ownership is not violated while guarding against {failure_mode}."
    )


def build_problem_case(
    family: dict[str, object],
    family_index: int,
    kind_index: int,
    case_kind: str,
    item_index: int,
) -> ProblemCase:
    failure_mode = _select(FAILURE_MODES, _failure_mode_index(family_index, kind_index, item_index))
    input_pattern = _select(INPUT_PATTERNS, _input_pattern_index(family_index, kind_index, item_index))
    state_pattern = _select(STATE_PATTERNS, _state_pattern_index(family_index, kind_index, item_index))
    oracle_type = _select(ORACLE_TYPES, _oracle_type_index(family_index, kind_index, item_index))
    importance = _select(IMPORTANCE_LEVELS, family_index + kind_index + item_index)
    family_name = str(family["name"])
    kind_code = KIND_CODES[case_kind]
    case_id = f"PC-{family_index + 1:02d}-{kind_code}-{item_index + 1:02d}"
    actors = tuple(family["actors"])
    side_effects = tuple(family["side_effects"])

    return ProblemCase(
        case_id=case_id,
        title=_case_title(family_name, case_kind, failure_mode, input_pattern),
        software_domain=str(family["domain"]),
        workflow_family=family_name,
        software_structure=str(family["structure"]),
        operation_boundary=str(family["boundary"]),
        actors=actors,
        external_inputs=(
            input_pattern,
            f"{family_name}_event_{item_index + 1}",
        ),
        initial_state_shape=state_pattern,
        state_transition_focus=_state_transition_focus(family, failure_mode, state_pattern),
        side_effects=side_effects,
        expected_behavior=_expected_behavior(
            family,
            case_kind,
            failure_mode,
            input_pattern,
            state_pattern,
        ),
        forbidden_behavior=_forbidden_behavior(family, case_kind, failure_mode, state_pattern),
        failure_mode=failure_mode,
        evidence_to_check=_evidence(
            family,
            case_kind,
            failure_mode,
            input_pattern,
            state_pattern,
        ),
        oracle_type=oracle_type,
        case_kind=case_kind,
        importance=importance,
        non_goals=(
            "Does not require a real database, network service, clock, random source, or external API.",
            "Does not assert implementation ownership beyond the problem statement itself.",
        ),
        notes=(
            f"Real software problem case for {family_name}; designed as corpus intent, "
            f"not as an implementation assignment."
        ),
        metadata={
            "corpus_section": "base_1500",
            "matrix_kind": "broad_coverage",
        },
    )


def _gap_area_item(area: dict[str, object], field_name: str, index: int) -> str:
    values = tuple(str(item) for item in area[field_name])
    return _select(values, index)


def _gap_case_kind(item_index: int) -> str:
    return _select(GAP_KIND_SEQUENCE, item_index)


def _gap_expected_behavior(
    area: dict[str, object],
    family: dict[str, object],
    case_kind: str,
    input_pattern: str,
    state_pattern: str,
    failure_mode: str,
    item_index: int,
) -> str:
    area_name = str(area["name"])
    boundary = str(family["boundary"])
    if case_kind == "positive_correct_case":
        return (
            f"{boundary} resolves {area_name} case {item_index + 1} for {input_pattern} "
            f"from {state_pattern} without {failure_mode}; evidence remains traceable."
        )
    if case_kind == "negative_broken_case":
        return (
            f"{boundary} should expose {failure_mode} in {area_name} case {item_index + 1} "
            f"when {input_pattern} reaches {state_pattern}."
        )
    if case_kind == "boundary_edge_case":
        return (
            f"{boundary} handles the {area_name} boundary condition {input_pattern} "
            f"deterministically from {state_pattern}."
        )
    if case_kind == "invalid_initial_state_case":
        return (
            f"{boundary} reports invalid {area_name} starting state {state_pattern} "
            f"before accepting side effects."
        )
    return (
        f"{boundary} must not loop, wait forever, or make success unreachable for "
        f"{area_name} case {item_index + 1} involving {failure_mode}."
    )


def _gap_forbidden_behavior(
    area: dict[str, object],
    family: dict[str, object],
    case_kind: str,
    failure_mode: str,
) -> tuple[str, ...]:
    area_name = str(area["name"])
    side_effects = tuple(str(item) for item in family["side_effects"])
    primary_side_effect = side_effects[0]
    if case_kind == "positive_correct_case":
        return (
            f"Report success while preserving hidden {failure_mode}.",
            f"Modify {primary_side_effect} without evidence for {area_name}.",
        )
    if case_kind == "negative_broken_case":
        return (
            f"Normalize away {failure_mode} during {area_name} review.",
            f"Hide raw state that proves {failure_mode}.",
        )
    if case_kind == "boundary_edge_case":
        return (
            f"Drop the {area_name} boundary input silently.",
            "Produce an output that the next function block cannot consume.",
        )
    if case_kind == "invalid_initial_state_case":
        return (
            f"Continue from invalid {area_name} state as if it were clean.",
            f"Create {primary_side_effect} before reporting the invalid state.",
        )
    return (
        f"Remain in a {area_name} cycle without modeled progress.",
        "Treat unreachable success as acceptable without review evidence.",
    )


def _gap_evidence(
    area: dict[str, object],
    family: dict[str, object],
    case_kind: str,
    input_pattern: str,
    state_pattern: str,
    failure_mode: str,
    item_index: int,
) -> tuple[str, ...]:
    area_name = str(area["name"])
    evidence_focus = str(area["evidence_focus"])
    side_effects = tuple(str(item) for item in family["side_effects"])
    primary_side_effect = side_effects[0]
    if case_kind == "positive_correct_case":
        return (
            f"{area_name} case {item_index + 1} preserves {evidence_focus}.",
            f"{primary_side_effect} count follows the expected identity or boundary rule.",
            f"Trace for {input_pattern} from {state_pattern} contains no {failure_mode}.",
        )
    if case_kind == "negative_broken_case":
        return (
            f"Counterexample names {failure_mode} in {area_name}.",
            f"Raw observed state exposes {evidence_focus}.",
            f"Trace step shows where {input_pattern} diverges from expected behavior.",
        )
    if case_kind == "boundary_edge_case":
        return (
            f"Boundary input {input_pattern} is consumed by a named branch.",
            f"Downstream compatibility is checked for {area_name}.",
            f"State {state_pattern} has an explicit transition or explicit rejection.",
        )
    if case_kind == "invalid_initial_state_case":
        return (
            f"Initial state predicate flags {state_pattern}.",
            f"No new {primary_side_effect} is created before invalid state reporting.",
            f"The report carries {area_name} evidence: {evidence_focus}.",
        )
    return (
        f"Reachability or loop report identifies {area_name} case {item_index + 1}.",
        f"Cycle, stuck state, or unreachable success evidence mentions {failure_mode}.",
        "Known limitations are labeled instead of being counted as pass.",
    )


def build_gap_problem_case(
    area: dict[str, object],
    area_index: int,
    item_index: int,
) -> ProblemCase:
    family_index = (area_index * 5 + item_index * 3) % len(WORKFLOW_FAMILIES)
    family = WORKFLOW_FAMILIES[family_index]
    area_name = str(area["name"])
    case_kind = _gap_case_kind(item_index)
    failure_mode = _gap_area_item(area, "failure_modes", item_index + area_index)
    input_pattern = _gap_area_item(area, "inputs", item_index * 2 + area_index)
    state_pattern = _gap_area_item(area, "states", item_index * 3 + area_index)
    oracle_type = _gap_area_item(area, "oracles", item_index + family_index)
    importance = _select(IMPORTANCE_LEVELS, item_index + area_index + 1)
    family_name = str(family["name"])
    case_id = f"GC-{area_index + 1:02d}-{item_index + 1:03d}"
    side_effects = tuple(str(item) for item in family["side_effects"])

    return ProblemCase(
        case_id=case_id,
        title=(
            f"{area_name}: {case_kind.replace('_', ' ')} for "
            f"{failure_mode.replace('_', ' ')} in {family_name}"
        ),
        software_domain=str(area["domain"]),
        workflow_family=family_name,
        software_structure=(
            f"{family['structure']} with gap focus on {area_name.replace('_', ' ')}"
        ),
        operation_boundary=str(family["boundary"]),
        actors=tuple(str(item) for item in family["actors"]),
        external_inputs=(
            input_pattern,
            f"{area_name}_stimulus_{item_index + 1}",
            f"{family_name}_context",
        ),
        initial_state_shape=state_pattern,
        state_transition_focus=(
            f"Stress {area_name} through {family['boundary']} and verify "
            f"{area['evidence_focus']}."
        ),
        side_effects=side_effects,
        expected_behavior=_gap_expected_behavior(
            area,
            family,
            case_kind,
            input_pattern,
            state_pattern,
            failure_mode,
            item_index,
        ),
        forbidden_behavior=_gap_forbidden_behavior(area, family, case_kind, failure_mode),
        failure_mode=failure_mode,
        evidence_to_check=_gap_evidence(
            area,
            family,
            case_kind,
            input_pattern,
            state_pattern,
            failure_mode,
            item_index,
        ),
        oracle_type=oracle_type,
        case_kind=case_kind,
        importance=importance,
        non_goals=(
            "Does not require a live external service, database, clock, random source, or API call.",
            "Does not assert that the case is executable by the current runtime.",
        ),
        notes=(
            f"Gap-focused real software problem case for {area_name}; it extends "
            "the broad corpus with high-risk workflow situations."
        ),
        metadata={
            "corpus_section": "gap_500",
            "gap_focus_area": area_name,
            "gap_focus_quota": int(area["quota"]),
        },
    )


def build_gap_problem_cases() -> tuple[ProblemCase, ...]:
    cases: list[ProblemCase] = []
    for area_index, area in enumerate(GAP_FOCUS_AREAS):
        quota = int(area["quota"])
        for item_index in range(quota):
            cases.append(build_gap_problem_case(area, area_index, item_index))
    return tuple(cases)


def build_pressure_problem_case(
    area: dict[str, object],
    area_index: int,
    item_index: int,
) -> ProblemCase:
    family = WORKFLOW_FAMILIES[item_index % len(WORKFLOW_FAMILIES)]
    area_name = str(area["name"])
    family_name = str(family["name"])
    case_kind = str(area["case_kind"])
    failure_mode = str(area["failure_mode"])
    input_pattern = str(area["input_pattern"])
    state_pattern = str(area["state_pattern"])
    oracle_type = str(area["oracle_type"])
    side_effects = tuple(str(item) for item in family["side_effects"])
    primary_side_effect = side_effects[0]
    case_id = f"PR-{area_index + 1:02d}-{item_index + 1:03d}"

    expected_status = str(area["expected_status"])
    if expected_status == "known_limitation":
        expected_behavior = (
            f"{family['boundary']} exposes a cycle with an escape edge for "
            f"{family_name}; current evidence must preserve the limitation label "
            "instead of treating the branch as proven terminating."
        )
        forbidden_behavior = (
            "Relabel a progress limitation as a normal pass.",
            "Hide the cycle edge just because an escape edge exists.",
        )
    elif expected_status == "violation":
        expected_behavior = (
            f"{family['boundary']} should expose {failure_mode} for {family_name} "
            f"when {input_pattern} reaches {state_pattern}."
        )
        forbidden_behavior = (
            f"Normalize away {failure_mode} during pressure review.",
            f"Create or preserve {primary_side_effect} without raw evidence.",
        )
    else:
        expected_behavior = (
            f"{family['boundary']} keeps benchmark artifact behavior stable for "
            f"{family_name} while preserving expected-vs-observed fields."
        )
        forbidden_behavior = (
            "Drop status fields from the machine-readable report.",
            "Silently convert a limitation or expected violation into a pass.",
        )

    return ProblemCase(
        case_id=case_id,
        title=(
            f"{area_name}: {case_kind.replace('_', ' ')} for "
            f"{failure_mode.replace('_', ' ')} in {family_name}"
        ),
        software_domain=str(area["domain"]),
        workflow_family=family_name,
        software_structure=(
            f"{family['structure']} under pressure focus {area_name.replace('_', ' ')}"
        ),
        operation_boundary=str(family["boundary"]),
        actors=tuple(str(item) for item in family["actors"]),
        external_inputs=(
            input_pattern,
            f"{area_name}_pressure_{item_index + 1}",
            f"{family_name}_context",
        ),
        initial_state_shape=state_pattern,
        state_transition_focus=(
            f"Stress {area_name} through {family['boundary']} and preserve "
            f"{area['evidence_focus']}."
        ),
        side_effects=side_effects,
        expected_behavior=expected_behavior,
        forbidden_behavior=forbidden_behavior,
        failure_mode=failure_mode,
        evidence_to_check=(
            f"Pressure focus {area_name} preserves {area['evidence_focus']}.",
            f"Observed status matches expected status {expected_status}.",
            f"Trace, graph, or report evidence names {failure_mode}.",
        ),
        oracle_type=oracle_type,
        case_kind=case_kind,
        importance="critical",
        non_goals=(
            "Does not require a live external service, database, clock, random source, or API call.",
            "Does not assign this case to a release, package, command-line wrapper, or external integration.",
        ),
        notes=(
            f"Pressure-baseline real software case for {area_name}; it is part "
            "of the main durable corpus and must keep expected-vs-observed status explicit."
        ),
        metadata={
            "corpus_section": "pressure_100",
            "pressure_focus_area": area_name,
            "pressure_focus_quota": int(area["quota"]),
            "pressure_expected_status": expected_status,
        },
    )


def build_pressure_problem_cases() -> tuple[ProblemCase, ...]:
    cases: list[ProblemCase] = []
    for area_index, area in enumerate(PRESSURE_FOCUS_AREAS):
        quota = int(area["quota"])
        for item_index in range(quota):
            cases.append(build_pressure_problem_case(area, area_index, item_index))
    return tuple(cases)


def build_problem_cases() -> tuple[ProblemCase, ...]:
    cases: list[ProblemCase] = []
    for family_index, family in enumerate(WORKFLOW_FAMILIES):
        for kind_index, (case_kind, quota) in enumerate(CASE_KIND_QUOTAS):
            for item_index in range(quota):
                cases.append(
                    build_problem_case(
                        family=family,
                        family_index=family_index,
                        kind_index=kind_index,
                        case_kind=case_kind,
                        item_index=item_index,
                    )
                )
    cases.extend(build_gap_problem_cases())
    cases.extend(build_pressure_problem_cases())
    return tuple(cases)


def build_problem_corpus() -> ProblemCorpus:
    return ProblemCorpus(
        build_problem_cases(),
        name="real_software_problem_corpus",
        description=(
            "Roadmap-independent corpus of real software workflow problem cases: "
            "1500 broad-coverage cases, 500 gap-focused stress cases, and 100 "
            "pressure-baseline cases. Cases describe test intent, not current "
            "support or release ownership."
        ),
    )


def review_problem_corpus() -> ProblemCorpusReport:
    return build_problem_corpus_report(
        build_problem_corpus(),
        min_cases=2100,
        min_workflow_families=20,
        min_failure_modes=20,
        min_cases_per_workflow_family=50,
        min_loop_or_stuck_cases=100,
        min_invalid_initial_state_cases=100,
        summary="Real software problem corpus quality review: base 1500 plus gap-focused 500 plus pressure-baseline 100.",
    )


__all__ = [
    "build_problem_case",
    "build_gap_problem_case",
    "build_gap_problem_cases",
    "build_pressure_problem_case",
    "build_pressure_problem_cases",
    "build_problem_cases",
    "build_problem_corpus",
    "review_problem_corpus",
]
