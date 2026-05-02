import unittest
from dataclasses import dataclass

from flowguard import (
    GraphEdge,
    LoopCheckConfig,
    Trace,
    TraceStep,
    check_loops,
    graph_to_mermaid_text,
    loop_report_to_mermaid_text,
    mermaid_code_block,
    trace_to_mermaid_text,
)


@dataclass(frozen=True)
class State:
    name: str


class MermaidExportTests(unittest.TestCase):
    def test_trace_exports_mermaid_source_without_changing_text_format(self):
        trace = Trace(
            initial_state=State('new "quoted"'),
            external_inputs=("job|1",),
            steps=(
                TraceStep(
                    external_input="job|1",
                    function_name="RecordJob",
                    function_input="job|1",
                    function_output='added "yes"',
                    old_state=State("new"),
                    new_state=State("done <ok>"),
                    label="record|added",
                ),
            ),
        )

        source = trace_to_mermaid_text(trace)

        self.assertTrue(source.startswith("flowchart TD"))
        self.assertIn("RecordJob", source)
        self.assertIn("&quot;yes&quot;", source)
        self.assertIn("record&#124;added", source)
        self.assertIn("&lt;ok&gt;", source)
        self.assertNotIn("```", source)
        self.assertNotIn("flowchart", trace.format_text())

    def test_graph_exports_mermaid_source_with_initial_state_style(self):
        start = State("start")
        done = State("done")
        edges = (GraphEdge(start, done, "finish", reason="terminal"),)

        source = graph_to_mermaid_text(
            edges,
            initial_states=(start,),
            direction="LR",
            include_reasons=True,
        )

        self.assertTrue(source.startswith("flowchart LR"))
        self.assertIn("State(name='start')", source)
        self.assertIn("finish: terminal", source)
        self.assertIn("classDef flowguardInitial", source)

    def test_loop_report_exports_reachable_graph_source(self):
        start = State("start")
        done = State("done")

        def transition(state):
            if state == start:
                return (GraphEdge(start, done, "finish"),)
            return ()

        report = check_loops(
            LoopCheckConfig(
                initial_states=(start,),
                transition_fn=transition,
                is_terminal=lambda state: state == done,
                is_success=lambda state: state == done,
                required_success=True,
            )
        )

        source = loop_report_to_mermaid_text(report)

        self.assertTrue(report.ok)
        self.assertIn("flowchart TD", source)
        self.assertIn("finish", source)
        self.assertNotIn("flowchart", report.format_text())

    def test_code_block_wraps_source_for_markdown(self):
        source = mermaid_code_block("flowchart TD\n  A --> B\n")

        self.assertEqual("```mermaid\nflowchart TD\n  A --> B\n```", source)


if __name__ == "__main__":
    unittest.main()
