import unittest

from flowguard.loop import GraphEdge, bottom_sccs, tarjan_scc


class LoopDetectionSccTests(unittest.TestCase):
    def test_tarjan_detects_simple_scc(self):
        edges = (
            GraphEdge("a", "b", "a_to_b"),
            GraphEdge("b", "a", "b_to_a"),
            GraphEdge("b", "c", "b_to_c"),
        )

        components = tarjan_scc(("a", "b", "c"), edges)
        component_sets = {frozenset(component) for component in components}

        self.assertIn(frozenset(("a", "b")), component_sets)
        self.assertIn(frozenset(("c",)), component_sets)

    def test_bottom_sccs_exclude_components_with_escape_edge(self):
        edges = (
            GraphEdge("a", "b", "a_to_b"),
            GraphEdge("b", "a", "b_to_a"),
            GraphEdge("b", "c", "b_to_c"),
        )

        components = tarjan_scc(("a", "b", "c"), edges)
        bottoms = bottom_sccs(components, edges)
        bottom_sets = {frozenset(component) for component in bottoms}

        self.assertNotIn(frozenset(("a", "b")), bottom_sets)
        self.assertIn(frozenset(("c",)), bottom_sets)


if __name__ == "__main__":
    unittest.main()
