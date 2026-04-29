import unittest
from dataclasses import dataclass

from flowguard.packs import CachePack, DeduplicationPack, RetryPack, SideEffectPack
from flowguard.trace import Trace


@dataclass(frozen=True)
class Item:
    key: str
    value: str = "v"


@dataclass(frozen=True)
class State:
    records: tuple[Item, ...] = ()
    cache: tuple[Item, ...] = ()
    source: tuple[Item, ...] = ()
    attempts: tuple[Item, ...] = ()
    effects: tuple[Item, ...] = ()


class PackTests(unittest.TestCase):
    def test_deduplication_pack_builds_duplicate_invariants_and_scenarios(self):
        pack = DeduplicationPack(lambda state: state.records, lambda item: item.key, value_name="record")
        invariants = pack.invariants()

        self.assertEqual(("no_duplicate_records", "record_at_most_once"), tuple(item.name for item in invariants))
        result = invariants[0].check(
            State(records=(Item("a"), Item("a"))),
            Trace(),
        )
        self.assertFalse(result.ok)
        scenarios = pack.scenarios(initial_states=(State(),), inputs=("a", "b"), max_scenarios=4)
        self.assertEqual(4, len(scenarios))
        self.assertIn("deduplication", scenarios[0].tags)

    def test_cache_pack_builds_cache_consistency_invariant(self):
        pack = CachePack(
            cache_selector=lambda state: state.cache,
            source_selector=lambda state: state.source,
            key=lambda item: item.key,
            value=lambda item: item.value,
            cache_name="score_cache",
            source_name="score_source",
        )
        invariant = pack.invariants()[0]

        self.assertEqual("score_cache_matches_score_source", invariant.name)
        result = invariant.check(
            State(cache=(Item("a", "low"),), source=(Item("a", "high"),)),
            Trace(),
        )
        self.assertFalse(result.ok)

    def test_retry_pack_is_optional_without_selectors(self):
        pack = RetryPack()

        self.assertEqual((), pack.invariants())
        self.assertEqual(2, pack.suggested_max_sequence_length)
        scenarios = pack.scenarios(initial_states=(State(),), inputs=("a", "b"), max_scenarios=3)
        self.assertEqual(3, len(scenarios))
        self.assertIn("retry", scenarios[0].tags)

    def test_side_effect_pack_builds_at_most_once_invariant(self):
        pack = SideEffectPack(lambda state: state.effects, lambda item: item.key)
        invariant = pack.invariants()[0]

        self.assertEqual("side_effect_at_most_once", invariant.name)
        result = invariant.check(
            State(effects=(Item("a"), Item("a"))),
            Trace(),
        )
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
