import unittest
from dataclasses import dataclass

from flowguard.loop import GraphEdge, LoopCheckConfig, check_loops


@dataclass(frozen=True)
class State:
    name: str


def edge(old, new, label):
    return GraphEdge(old_state=old, new_state=new, label=label)


class LoopCoreTests(unittest.TestCase):
    def test_bottom_scc_without_terminal_is_reported(self):
        a = State("a")
        b = State("b")

        def transition(state):
            if state == a:
                return (edge(a, b, "a_to_b"),)
            if state == b:
                return (edge(b, b, "b_to_b"),)
            return ()

        report = check_loops(
            LoopCheckConfig(
                initial_states=(a,),
                transition_fn=transition,
                is_terminal=lambda state: False,
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(1, len(report.non_terminating_components))

    def test_nonterminal_dead_state_is_reported(self):
        start = State("start")
        dead = State("dead")

        def transition(state):
            if state == start:
                return (edge(start, dead, "to_dead"),)
            return ()

        report = check_loops(
            LoopCheckConfig(
                initial_states=(start,),
                transition_fn=transition,
                is_terminal=lambda state: state.name == "done",
                is_success=lambda state: state.name == "done",
                required_success=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(dead, report.stuck_states)
        self.assertTrue(report.unreachable_success)

    def test_terminal_with_outgoing_edge_is_reported(self):
        start = State("start")
        done = State("done")
        next_state = State("next")

        def transition(state):
            if state == start:
                return (edge(start, done, "finish"),)
            if state == done:
                return (edge(done, next_state, "leak"),)
            return ()

        report = check_loops(
            LoopCheckConfig(
                initial_states=(start,),
                transition_fn=transition,
                is_terminal=lambda state: state.name == "done",
                is_success=lambda state: state.name == "done",
                required_success=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(done, report.terminal_with_outgoing_edges[0].state)


if __name__ == "__main__":
    unittest.main()
