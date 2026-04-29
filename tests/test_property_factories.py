import unittest
from dataclasses import dataclass

from flowguard.checks import (
    PROPERTY_CLASSES_KEY,
    all_items_have_source,
    at_most_once_by,
    cache_matches_source,
    forbid_label_after,
    no_contradictory_values,
    no_duplicate_by,
    only_named_block_writes,
    require_label_order,
)
from flowguard.trace import Trace, TraceStep


@dataclass(frozen=True)
class Record:
    job_id: str
    value: str


@dataclass(frozen=True)
class State:
    records: tuple[Record, ...] = ()
    sources: tuple[Record, ...] = ()
    attempts: tuple[Record, ...] = ()
    cache: tuple[Record, ...] = ()


def _metadata(result):
    return dict(result.metadata)


def _invariant_metadata(invariant):
    return dict(invariant.metadata)


class PropertyFactoryTests(unittest.TestCase):
    def test_standard_factories_tag_property_classes_for_audit(self):
        duplicate_invariant = no_duplicate_by(
            name="job_records_are_valid",
            description="records are valid",
            selector=lambda state: state.records,
            key=lambda record: record.job_id,
        )
        once_invariant = at_most_once_by(
            name="attempts_are_valid",
            description="attempt records are valid",
            selector=lambda state: state.attempts,
            key=lambda attempt: attempt.job_id,
        )
        cache_invariant = cache_matches_source(
            name="scores_are_valid",
            description="scores are valid",
            cache_selector=lambda state: state.cache,
            source_selector=lambda state: state.sources,
            key=lambda record: record.job_id,
            value=lambda record: record.value,
        )

        self.assertIn(
            "deduplication",
            _invariant_metadata(duplicate_invariant)[PROPERTY_CLASSES_KEY],
        )
        self.assertIn(
            "at_most_once",
            _invariant_metadata(once_invariant)[PROPERTY_CLASSES_KEY],
        )
        self.assertIn(
            "cache_consistency",
            _invariant_metadata(cache_invariant)[PROPERTY_CLASSES_KEY],
        )

    def test_no_duplicate_by_reports_duplicate_keys(self):
        invariant = no_duplicate_by(
            name="unique_records_by_job",
            description="records are unique by job id",
            selector=lambda state: state.records,
            key=lambda record: record.job_id,
            value_name="application_record",
        )

        result = invariant.check(
            State(records=(Record("job_1", "apply"), Record("job_1", "apply"))),
            Trace(),
        )

        self.assertFalse(result.ok)
        self.assertIn("duplicate application_record keys", result.message)
        self.assertEqual(("job_1",), _metadata(result)["duplicate_keys"])

    def test_at_most_once_by_reports_repeated_attempts(self):
        invariant = at_most_once_by(
            name="score_once",
            description="score attempts are idempotent",
            selector=lambda state: state.attempts,
            key=lambda attempt: attempt.job_id,
            value_name="score_attempt",
        )

        result = invariant.check(
            State(attempts=(Record("job_1", "first"), Record("job_1", "retry"))),
            Trace(),
        )

        self.assertFalse(result.ok)
        self.assertIn("score_attempts occurred more than once", result.message)
        self.assertEqual(("job_1",), _metadata(result)["repeated_keys"])

    def test_all_items_have_source_reports_missing_source_keys(self):
        invariant = all_items_have_source(
            name="records_have_scores",
            description="every application record has a source score",
            item_selector=lambda state: state.records,
            source_selector=lambda state: state.sources,
            item_key=lambda record: record.job_id,
            source_key=lambda source: source.job_id,
            item_name="application_record",
            source_name="score",
        )

        result = invariant.check(
            State(
                records=(Record("job_1", "apply"), Record("job_2", "apply")),
                sources=(Record("job_1", "high"),),
            ),
            Trace(),
        )

        self.assertFalse(result.ok)
        self.assertIn("missing score keys", result.message)
        self.assertEqual(("job_2",), _metadata(result)["missing_source_keys"])

    def test_no_contradictory_values_reports_forbidden_pair(self):
        invariant = no_contradictory_values(
            name="no_apply_and_ignore",
            description="same job cannot be applied and ignored",
            selector=lambda state: state.records,
            key=lambda record: record.job_id,
            value=lambda record: record.value,
            forbidden_pairs=(("apply", "ignore"),),
            key_name="job_id",
            value_name="decision",
        )

        result = invariant.check(
            State(records=(Record("job_1", "apply"), Record("job_1", "ignore"))),
            Trace(),
        )

        self.assertFalse(result.ok)
        self.assertIn("contradictory decisions", result.message)
        self.assertEqual("job_1", _metadata(result)["contradictions"][0][0])

    def test_cache_matches_source_reports_missing_and_mismatched_keys(self):
        invariant = cache_matches_source(
            name="cache_consistent",
            description="cache agrees with source",
            cache_selector=lambda state: state.cache,
            source_selector=lambda state: state.sources,
            key=lambda record: record.job_id,
            value=lambda record: record.value,
            key_name="job_id",
            value_name="score",
            cache_name="score_cache",
            source_name="source_scores",
        )

        result = invariant.check(
            State(
                cache=(Record("job_1", "low"), Record("job_2", "high")),
                sources=(Record("job_1", "high"),),
            ),
            Trace(),
        )

        self.assertFalse(result.ok)
        metadata = _metadata(result)
        self.assertEqual(("job_2",), metadata["missing_source_keys"])
        self.assertEqual(("job_1",), metadata["mismatched_keys"])

    def test_only_named_block_writes_reports_unauthorized_state_write(self):
        old_state = State()
        new_state = State(records=(Record("job_1", "apply"),))
        trace = Trace(
            steps=(
                TraceStep(
                    external_input="job_1",
                    function_name="OtherBlock",
                    function_input="job_1",
                    function_output="job_1",
                    old_state=old_state,
                    new_state=new_state,
                    label="record_added",
                ),
            )
        )
        invariant = only_named_block_writes("records", "RecordBlock")

        result = invariant.check(new_state, trace)

        self.assertFalse(result.ok)
        self.assertIn("non-owner blocks", result.message)
        self.assertEqual("OtherBlock", _metadata(result)["unauthorized_writes"][0][1])

    def test_label_order_helpers_report_order_gaps(self):
        trace = Trace(
            steps=(
                TraceStep("job_1", "Record", "job_1", "job_1", State(), State(), "record_added"),
                TraceStep("job_1", "Validate", "job_1", "job_1", State(), State(), "validated"),
                TraceStep("job_1", "Cancel", "job_1", "job_1", State(), State(), "cancelled"),
                TraceStep("job_1", "Ship", "job_1", "job_1", State(), State(), "shipped"),
            )
        )

        order_result = require_label_order("validated", "record_added").check(State(), trace)
        after_result = forbid_label_after("cancelled", "shipped").check(State(), trace)

        self.assertFalse(order_result.ok)
        self.assertIn("without earlier 'validated'", order_result.message)
        self.assertEqual((1,), _metadata(order_result)["violating_after_positions"])
        self.assertFalse(after_result.ok)
        self.assertIn("appeared after 'cancelled'", after_result.message)
        self.assertEqual((4,), _metadata(after_result)["violating_forbidden_positions"])


if __name__ == "__main__":
    unittest.main()
