"""Convenience constructors for invariants and reachability checks."""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Mapping
from typing import Any, Callable, Iterable

from .core import Invariant, InvariantResult
from .explorer import ReachabilityCondition


StatePredicate = Callable[[Any], bool]
StateTracePredicate = Callable[[Any, Any], bool]
Selector = Callable[[Any], Iterable[Any]]
KeySelector = Callable[[Any], Hashable]
ValueSelector = Callable[[Any], Hashable]
PROPERTY_CLASSES_KEY = "property_classes"


def _property_metadata(*classes: str) -> dict[str, tuple[str, ...]]:
    normalized = tuple(
        dict.fromkeys(
            str(item).strip().lower()
            for item in classes
            if str(item).strip()
        )
    )
    return {PROPERTY_CLASSES_KEY: normalized}


def _group_items_by_key(items: Iterable[Any], key: KeySelector) -> dict[Hashable, list[Any]]:
    grouped: dict[Hashable, list[Any]] = {}
    for item in items:
        grouped.setdefault(key(item), []).append(item)
    return grouped


def _field_value(state: Any, field_name: str) -> Any:
    if isinstance(state, Mapping):
        return state[field_name]
    return getattr(state, field_name)


def _label_positions(trace: Any, label: str) -> tuple[int, ...]:
    return tuple(
        index
        for index, step in enumerate(getattr(trace, "steps", ()), start=1)
        if getattr(step, "label", "") == label
    )


def state_invariant(
    name: str,
    description: str,
    predicate: StateTracePredicate,
    message: str | Callable[[Any, Any], str] = "",
    metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
) -> Invariant:
    """Create an invariant from a `(state, trace) -> bool` predicate."""

    def check(state: Any, trace: Any) -> bool | InvariantResult:
        passed = bool(predicate(state, trace))
        if passed:
            return InvariantResult.pass_()
        rendered = message(state, trace) if callable(message) else message
        return InvariantResult.fail(rendered or f"invariant failed: {name}")

    return Invariant(name=name, description=description, predicate=check, metadata=metadata)


def no_duplicate_values(
    name: str,
    description: str,
    selector: Selector,
    value_name: str = "value",
) -> Invariant:
    """Require the selected values to contain no duplicates."""

    def check(state: Any, trace: Any) -> InvariantResult:
        del trace
        values = tuple(selector(state))
        counts = Counter(values)
        duplicates = tuple(value for value, count in counts.items() if count > 1)
        if not duplicates:
            return InvariantResult.pass_()
        return InvariantResult.fail(
            f"duplicate {value_name}s: {duplicates!r}",
            {"duplicates": duplicates},
        )

    return Invariant(
        name=name,
        description=description,
        predicate=check,
        metadata=_property_metadata("deduplication", "uniqueness"),
    )


def no_duplicate_by(
    name: str,
    description: str,
    selector: Selector,
    key: KeySelector,
    value_name: str = "value",
) -> Invariant:
    """Require selected items to be unique by a derived key."""

    def check(state: Any, trace: Any) -> InvariantResult:
        del trace
        items = tuple(selector(state))
        grouped = _group_items_by_key(items, key)
        duplicate_groups = tuple(
            (item_key, tuple(group))
            for item_key, group in grouped.items()
            if len(group) > 1
        )
        if not duplicate_groups:
            return InvariantResult.pass_()
        duplicate_keys = tuple(item_key for item_key, _group in duplicate_groups)
        return InvariantResult.fail(
            f"duplicate {value_name} keys: {duplicate_keys!r}",
            {
                "value_name": value_name,
                "duplicate_keys": duplicate_keys,
                "duplicate_items_by_key": duplicate_groups,
            },
        )

    return Invariant(
        name=name,
        description=description,
        predicate=check,
        metadata=_property_metadata("deduplication", "uniqueness"),
    )


def at_most_once_by(
    name: str,
    description: str,
    selector: Selector,
    key: KeySelector,
    value_name: str = "event",
) -> Invariant:
    """Require each key to appear at most once in events, attempts, or effects."""

    def check(state: Any, trace: Any) -> InvariantResult:
        del trace
        items = tuple(selector(state))
        grouped = _group_items_by_key(items, key)
        repeated_groups = tuple(
            (item_key, tuple(group))
            for item_key, group in grouped.items()
            if len(group) > 1
        )
        if not repeated_groups:
            return InvariantResult.pass_()
        repeated_keys = tuple(item_key for item_key, _group in repeated_groups)
        return InvariantResult.fail(
            f"{value_name}s occurred more than once for keys: {repeated_keys!r}",
            {
                "value_name": value_name,
                "repeated_keys": repeated_keys,
                "repeated_items_by_key": repeated_groups,
            },
        )

    return Invariant(
        name=name,
        description=description,
        predicate=check,
        metadata=_property_metadata("idempotency", "at_most_once", "side_effect"),
    )


def all_items_have_source(
    name: str,
    description: str,
    item_selector: Selector,
    source_selector: Selector,
    item_key: KeySelector,
    source_key: KeySelector,
    item_name: str = "item",
    source_name: str = "source",
) -> Invariant:
    """Require every downstream item to have a matching source object."""

    def check(state: Any, trace: Any) -> InvariantResult:
        del trace
        items = tuple(item_selector(state))
        sources = tuple(source_selector(state))
        source_keys = frozenset(source_key(source) for source in sources)
        missing = tuple(
            (item_key(item), item)
            for item in items
            if item_key(item) not in source_keys
        )
        if not missing:
            return InvariantResult.pass_()
        missing_keys = tuple(key_value for key_value, _item in missing)
        return InvariantResult.fail(
            f"{item_name}s missing {source_name} keys: {missing_keys!r}",
            {
                "item_name": item_name,
                "source_name": source_name,
                "missing_source_keys": missing_keys,
                "orphan_items": missing,
                "source_keys": tuple(sorted(source_keys, key=repr)),
            },
        )

    return Invariant(
        name=name,
        description=description,
        predicate=check,
        metadata=_property_metadata("source_traceability"),
    )


def no_contradictory_values(
    name: str,
    description: str,
    selector: Selector,
    key: KeySelector,
    value: ValueSelector,
    forbidden_pairs: Iterable[tuple[Hashable, Hashable]] | None = None,
    forbidden_sets: Iterable[Iterable[Hashable]] | None = None,
    key_name: str = "key",
    value_name: str = "value",
) -> Invariant:
    """Require one key not to accumulate mutually exclusive values."""

    explicit_forbidden = tuple(
        frozenset(pair)
        for pair in tuple(forbidden_pairs or ())
    ) + tuple(
        frozenset(values)
        for values in tuple(forbidden_sets or ())
    )

    def check(state: Any, trace: Any) -> InvariantResult:
        del trace
        grouped: dict[Hashable, set[Hashable]] = {}
        for item in tuple(selector(state)):
            grouped.setdefault(key(item), set()).add(value(item))

        contradictions: list[tuple[Hashable, tuple[Hashable, ...], tuple[Hashable, ...]]] = []
        for key_value, values in grouped.items():
            candidates = explicit_forbidden or (frozenset(values),)
            for forbidden in candidates:
                if len(forbidden) < 2:
                    continue
                if forbidden.issubset(values):
                    contradictions.append(
                        (
                            key_value,
                            tuple(sorted(values, key=repr)),
                            tuple(sorted(forbidden, key=repr)),
                        )
                    )
                    break

        if not contradictions:
            return InvariantResult.pass_()
        bad_keys = tuple(key_value for key_value, _values, _forbidden in contradictions)
        return InvariantResult.fail(
            f"contradictory {value_name}s for {key_name}s: {bad_keys!r}",
            {
                "key_name": key_name,
                "value_name": value_name,
                "contradictions": tuple(contradictions),
            },
        )

    return Invariant(
        name=name,
        description=description,
        predicate=check,
        metadata=_property_metadata("consistency", "contradiction"),
    )


def cache_matches_source(
    name: str,
    description: str,
    cache_selector: Selector,
    source_selector: Selector,
    key: KeySelector,
    value: ValueSelector,
    key_name: str = "key",
    value_name: str = "value",
    cache_name: str = "cache",
    source_name: str = "source",
) -> Invariant:
    """Require cached values to match the source of truth for the same key."""

    def check(state: Any, trace: Any) -> InvariantResult:
        del trace
        cache_items = tuple(cache_selector(state))
        source_items = tuple(source_selector(state))

        source_values: dict[Hashable, set[Hashable]] = {}
        for source in source_items:
            source_values.setdefault(key(source), set()).add(value(source))

        missing_source: list[tuple[Hashable, Any]] = []
        mismatches: list[tuple[Hashable, Hashable, tuple[Hashable, ...]]] = []
        inconsistent_sources: list[tuple[Hashable, tuple[Hashable, ...]]] = []
        for source_key, values in source_values.items():
            if len(values) > 1:
                inconsistent_sources.append((source_key, tuple(sorted(values, key=repr))))

        for cache in cache_items:
            cache_key = key(cache)
            cache_value = value(cache)
            expected_values = source_values.get(cache_key)
            if expected_values is None:
                missing_source.append((cache_key, cache))
                continue
            if cache_value not in expected_values:
                mismatches.append(
                    (
                        cache_key,
                        cache_value,
                        tuple(sorted(expected_values, key=repr)),
                    )
                )

        if not missing_source and not mismatches and not inconsistent_sources:
            return InvariantResult.pass_()
        missing_keys = tuple(item_key for item_key, _cache in missing_source)
        mismatch_keys = tuple(item_key for item_key, _cache_value, _source_values in mismatches)
        inconsistent_keys = tuple(item_key for item_key, _source_values in inconsistent_sources)
        return InvariantResult.fail(
            (
                f"{cache_name} does not match {source_name} for {key_name}s: "
                f"missing={missing_keys!r} mismatched={mismatch_keys!r} "
                f"inconsistent_source={inconsistent_keys!r}"
            ),
            {
                "key_name": key_name,
                "value_name": value_name,
                "cache_name": cache_name,
                "source_name": source_name,
                "missing_source_keys": missing_keys,
                "mismatched_keys": mismatch_keys,
                "inconsistent_source_keys": inconsistent_keys,
                "missing_source_cache_items": tuple(missing_source),
                "mismatches": tuple(mismatches),
                "inconsistent_sources": tuple(inconsistent_sources),
            },
        )

    return Invariant(
        name=name,
        description=description,
        predicate=check,
        metadata=_property_metadata("cache", "cache_consistency", "source_consistency"),
    )


def only_named_block_writes(
    field_name: str,
    owner_function_name: str,
    name: str | None = None,
    description: str = "",
) -> Invariant:
    """Require a state field to be changed only by one named function block."""

    invariant_name = name or f"only_{owner_function_name}_writes_{field_name}"
    invariant_description = (
        description
        or f"state field {field_name!r} may only be written by {owner_function_name!r}"
    )

    def check(state: Any, trace: Any) -> InvariantResult:
        del state
        unauthorized: list[tuple[int, str, Any, Any, str]] = []
        for index, step in enumerate(getattr(trace, "steps", ()), start=1):
            try:
                old_value = _field_value(step.old_state, field_name)
                new_value = _field_value(step.new_state, field_name)
            except (AttributeError, KeyError) as exc:
                return InvariantResult.fail(
                    f"state field {field_name!r} was missing while checking writer ownership",
                    {"field_name": field_name, "error": str(exc), "step_index": index},
                )
            if old_value == new_value:
                continue
            function_name = getattr(step, "function_name", "")
            if function_name != owner_function_name:
                unauthorized.append(
                    (
                        index,
                        function_name,
                        old_value,
                        new_value,
                        getattr(step, "label", ""),
                    )
                )
        if not unauthorized:
            return InvariantResult.pass_()
        writers = tuple((index, function_name) for index, function_name, *_rest in unauthorized)
        return InvariantResult.fail(
            f"field {field_name!r} was written by non-owner blocks: {writers!r}",
            {
                "field_name": field_name,
                "owner_function_name": owner_function_name,
                "unauthorized_writes": tuple(unauthorized),
            },
        )

    return Invariant(
        name=invariant_name,
        description=invariant_description,
        predicate=check,
        metadata=_property_metadata("module_boundary", "ownership"),
    )


def require_label_order(
    before_label: str,
    after_label: str,
    name: str | None = None,
    description: str = "",
) -> Invariant:
    """Require `before_label` to appear before every `after_label` in a trace."""

    invariant_name = name or f"label_order:{before_label}_before_{after_label}"
    invariant_description = (
        description
        or f"label {before_label!r} must appear before label {after_label!r}"
    )

    def check(state: Any, trace: Any) -> InvariantResult:
        del state
        before_positions = _label_positions(trace, before_label)
        after_positions = _label_positions(trace, after_label)
        violating_after = tuple(
            position
            for position in after_positions
            if not any(before_position < position for before_position in before_positions)
        )
        if not violating_after:
            return InvariantResult.pass_()
        return InvariantResult.fail(
            (
                f"label {after_label!r} appeared without earlier {before_label!r} "
                f"at positions: {violating_after!r}"
            ),
            {
                "before_label": before_label,
                "after_label": after_label,
                "before_positions": before_positions,
                "after_positions": after_positions,
                "violating_after_positions": violating_after,
            },
        )

    return Invariant(
        name=invariant_name,
        description=invariant_description,
        predicate=check,
        metadata=_property_metadata("trace_order"),
    )


def forbid_label_after(
    anchor_label: str,
    forbidden_label: str,
    name: str | None = None,
    description: str = "",
) -> Invariant:
    """Require `forbidden_label` not to appear after `anchor_label`."""

    invariant_name = name or f"forbid_label_after:{forbidden_label}_after_{anchor_label}"
    invariant_description = (
        description
        or f"label {forbidden_label!r} must not appear after label {anchor_label!r}"
    )

    def check(state: Any, trace: Any) -> InvariantResult:
        del state
        anchor_positions = _label_positions(trace, anchor_label)
        forbidden_positions = _label_positions(trace, forbidden_label)
        if not anchor_positions:
            return InvariantResult.pass_()
        first_anchor = min(anchor_positions)
        violating_forbidden = tuple(
            position
            for position in forbidden_positions
            if position > first_anchor
        )
        if not violating_forbidden:
            return InvariantResult.pass_()
        return InvariantResult.fail(
            (
                f"label {forbidden_label!r} appeared after {anchor_label!r} "
                f"at positions: {violating_forbidden!r}"
            ),
            {
                "anchor_label": anchor_label,
                "forbidden_label": forbidden_label,
                "anchor_positions": anchor_positions,
                "forbidden_positions": forbidden_positions,
                "violating_forbidden_positions": violating_forbidden,
            },
        )

    return Invariant(
        name=invariant_name,
        description=invariant_description,
        predicate=check,
        metadata=_property_metadata("trace_order", "forbidden_label"),
    )


def require_label(label: str, description: str = "") -> ReachabilityCondition:
    """Require at least one explored trace to include a label."""

    return ReachabilityCondition(
        name=f"label:{label}",
        description=description or f"label {label!r} must be reachable",
        predicate=lambda state, trace: trace.has_label(label),
    )


def require_reachable(
    name: str,
    predicate: StateTracePredicate,
    description: str = "",
) -> ReachabilityCondition:
    """Require at least one explored path to match a predicate."""

    return ReachabilityCondition(name=name, predicate=predicate, description=description)


__all__ = [
    "PROPERTY_CLASSES_KEY",
    "ReachabilityCondition",
    "all_items_have_source",
    "at_most_once_by",
    "cache_matches_source",
    "forbid_label_after",
    "no_duplicate_values",
    "no_duplicate_by",
    "no_contradictory_values",
    "only_named_block_writes",
    "require_label",
    "require_label_order",
    "require_reachable",
    "state_invariant",
]
