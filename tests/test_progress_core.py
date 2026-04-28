import json
import unittest
from dataclasses import dataclass

from flowguard.loop import GraphEdge
from flowguard.progress import (
    BoundedEventuallyProperty,
    ProgressCheckConfig,
    check_progress,
)


@dataclass(frozen=True)
class PState:
    phase: str
    remaining: int = 0


def edge(old, new, label):
    return GraphEdge(old_state=old, new_state=new, label=label)


class ProgressCoreTests(unittest.TestCase):
    def test_escape_edge_cycle_without_ranking_is_reported(self):
        start = PState("start")
        maybe = PState("maybe")
        rewrite = PState("rewrite")
        done = PState("done")

        def transition(state):
            if state == start:
                return (edge(start, maybe, "start"),)
            if state == maybe:
                return (
                    edge(maybe, rewrite, "cycle"),
                    edge(maybe, done, "escape"),
                )
            if state == rewrite:
                return (edge(rewrite, maybe, "back"),)
            return ()

        report = check_progress(
            ProgressCheckConfig(
                initial_states=(start,),
                transition_fn=transition,
                is_terminal=lambda state: state.phase == "done",
                is_success=lambda state: state.phase == "done",
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("potential_nontermination", report.finding_names())
        self.assertIn("missing_progress_guarantee", report.finding_names())

    def test_ranking_decrease_makes_escape_cycle_acceptable(self):
        start = PState("start", 2)
        maybe2 = PState("maybe", 2)
        rewrite1 = PState("rewrite", 1)
        maybe1 = PState("maybe", 1)
        done = PState("done", 0)

        def transition(state):
            if state == start:
                return (edge(start, maybe2, "start"),)
            if state == maybe2:
                return (
                    edge(maybe2, rewrite1, "rewrite_decreases"),
                    edge(maybe2, done, "escape"),
                )
            if state == rewrite1:
                return (edge(rewrite1, maybe1, "back"),)
            if state == maybe1:
                return (edge(maybe1, done, "escape_after_progress"),)
            return ()

        report = check_progress(
            ProgressCheckConfig(
                initial_states=(start,),
                transition_fn=transition,
                is_terminal=lambda state: state.phase == "done",
                is_success=lambda state: state.phase == "done",
                ranking_fn=lambda state: state.remaining,
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_bounded_eventually_property_reports_late_target(self):
        start = PState("start")
        middle = PState("middle")
        done = PState("done")

        def transition(state):
            if state == start:
                return (edge(start, middle, "slow"),)
            if state == middle:
                return (edge(middle, done, "finish"),)
            return ()

        report = check_progress(
            ProgressCheckConfig(
                initial_states=(start,),
                transition_fn=transition,
                is_terminal=lambda state: state.phase == "done",
                bounded_eventually=(
                    BoundedEventuallyProperty(
                        name="finish_within_one_step",
                        description="start must finish within one transition",
                        trigger=lambda state: state.phase == "start",
                        target=lambda state: state.phase == "done",
                        max_steps=1,
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("finish_within_one_step", report.finding_names())
        loaded = json.loads(report.to_json_text())
        self.assertIn("findings", loaded)


if __name__ == "__main__":
    unittest.main()
