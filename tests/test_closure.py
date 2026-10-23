"""Real handoff closure and parent-invariant behavior tests."""
import unittest
from dataclasses import replace
from flowguard.closure import MESH_CLOSURE_OUT_OF_SCOPE, MeshClosureJoin, MeshClosureModel, MeshClosureTerminal, MeshClosureTransition, closure_invariant, review_mesh_closure_model
from flowguard.core import FunctionResult
from flowguard.explorer import Explorer
from flowguard.workflow import Workflow

def closure_model(**kwargs):
    defaults = {'parent_model_id': 'checkout', 'root_entries': ('root_start',),
        'transitions': (MeshClosureTransition('start_payment', consumes=('root_start',), emits=('payment_result',),
        consumer_model_id='payment'), MeshClosureTransition('start_inventory', consumes=('root_start',),
        emits=('inventory_result',), consumer_model_id='inventory')), 'joins': (MeshClosureJoin('checkout_ready',
        required_inputs=('payment_result', 'inventory_result'), emits=('order_ready',)),),
        'terminals': (MeshClosureTerminal('order_complete', consumes=('order_ready',), terminal_kind='normal_exit'),)}
    defaults.update(kwargs)
    return MeshClosureModel(**defaults)

class ParentStep:
    name = 'ParentStep'

    def apply(self, value, state):
        return [FunctionResult(value, state)]

def parent_model(mesh):
    return Explorer(Workflow((ParentStep(),)), initial_states=(0,), external_inputs=(None,), max_sequence_length=1,
        progress_steps=0, invariants=(closure_invariant(mesh),))

class ClosureTests(unittest.TestCase):

    def test_mesh_closure_complete_model_can_continue(self):
        report = review_mesh_closure_model(closure_model(required_outputs=('inventory_result', 'payment_result')))
        self.assertTrue(report.ok)
        self.assertEqual('mesh_closure_green', report.decision)
        self.assertIn('order_ready', report.reachable_tokens)

    def test_mesh_closure_requires_root_entry(self):
        report = review_mesh_closure_model(closure_model(root_entries=(), required_outputs=('payment_result',)))
        self.assertFalse(report.ok)
        self.assertEqual('missing_root_entry', report.decision)
        self.assertIn('missing_root_entry', [finding.code for finding in report.findings])

    def test_repeat_input_loop_requires_repair_feedback(self):
        report = review_mesh_closure_model(closure_model(root_entries=('rejected_packet',),
            transitions=(MeshClosureTransition('retry_same_packet', consumes=('rejected_packet',),
            emits=('rejected_packet', 'blocked'), loop=True, repeat_input_tokens=('rejected_packet',),
            blocker_tokens=('blocked',), max_iterations=1),), joins=(), terminals=(MeshClosureTerminal('blocked',
            consumes=('blocked',)),)))
        self.assertFalse(report.ok)
        self.assertEqual('loop_repair_feedback_required', report.decision)
        self.assertIn('loop_repair_feedback_required', [finding.code for finding in report.findings])

    def test_repeat_input_loop_requires_structured_no_delta_disposition(self):
        report = review_mesh_closure_model(closure_model(root_entries=('rejected_packet',),
            transitions=(MeshClosureTransition('retry_same_packet', consumes=('rejected_packet',),
            emits=('rejected_packet', 'repair_feedback'), loop=True, progress_rule='agent should change the packet',
            repeat_input_tokens=('rejected_packet',), repair_feedback_tokens=('repair_feedback',)),), joins=(),
            terminals=(MeshClosureTerminal('retry_terminal', consumes=('repair_feedback',)),)))
        self.assertFalse(report.ok)
        self.assertEqual('loop_no_delta_disposition_required', report.decision)
        self.assertIn('loop_no_delta_disposition_required', [finding.code for finding in report.findings])

    def test_guarded_repeat_input_loop_can_close(self):
        report = review_mesh_closure_model(closure_model(root_entries=('rejected_packet',),
            transitions=(MeshClosureTransition('retry_same_packet', consumes=('rejected_packet',),
            emits=('repair_feedback', 'blocked'), loop=True, repeat_input_tokens=('rejected_packet',),
            repair_feedback_tokens=('repair_feedback',), blocker_tokens=('blocked',)),), joins=(),
            terminals=(MeshClosureTerminal('blocked', consumes=('blocked',)),)))
        self.assertTrue(report.ok, report.format_text())
        self.assertEqual('mesh_closure_green', report.decision)

    def test_mesh_closure_rejects_unconsumed_child_output(self):
        report = review_mesh_closure_model(closure_model(transitions=(MeshClosureTransition('start_payment',
            consumes=('root_start',), emits=('payment_result',), consumer_model_id='payment'),), joins=(),
            terminals=(MeshClosureTerminal('payment_done', consumes=('payment_result',)),),
            required_outputs=('manual_review_needed', 'payment_result')))
        self.assertFalse(report.ok)
        self.assertIn('unconsumed_child_output', [finding.code for finding in report.findings])

    def test_mesh_closure_rejects_unknown_output_reference(self):
        report = review_mesh_closure_model(closure_model(transitions=(MeshClosureTransition('foreign_consume',
            consumes=('foreign_output',), emits=('payment_result',)),), joins=(),
            terminals=(MeshClosureTerminal('payment_done', consumes=('payment_result',)),),
            required_outputs=('payment_result',)))
        self.assertFalse(report.ok)
        self.assertIn('unknown_closure_reference', [finding.code for finding in report.findings])

    def test_mesh_closure_rejects_incomplete_join(self):
        report = review_mesh_closure_model(closure_model(joins=(MeshClosureJoin('checkout_ready',
            required_inputs=('payment_result', 'inventory_result', 'tax_result'), emits=('order_ready',)),),
            required_outputs=('inventory_result', 'payment_result')))
        self.assertFalse(report.ok)
        self.assertIn('missing_join_point', [finding.code for finding in report.findings])

    def test_mesh_closure_rejects_terminal_leak(self):
        report = review_mesh_closure_model(closure_model(transitions=(MeshClosureTransition('start_payment',
            consumes=('root_start',), emits=('payment_result',)), MeshClosureTransition('start_inventory',
            consumes=('root_start',), emits=('inventory_result',))), joins=(),
            terminals=(MeshClosureTerminal('premature_done', consumes=('payment_result',)),),
            required_outputs=('inventory_result', 'payment_result')))
        self.assertFalse(report.ok)
        self.assertIn('terminal_leak', [finding.code for finding in report.findings])

    def test_mesh_closure_rejects_loop_without_progress(self):
        report = review_mesh_closure_model(closure_model(transitions=(MeshClosureTransition('retry_payment',
            consumes=('payment_result',), emits=('payment_result',), consumer_model_id='payment', loop=True),),
            joins=(), terminals=(MeshClosureTerminal('payment_done', consumes=('payment_result',)),),
            required_outputs=('payment_result',)))
        self.assertFalse(report.ok)
        self.assertIn('loop_progress_required', [finding.code for finding in report.findings])

    def test_mesh_closure_allows_bounded_loop(self):
        report = review_mesh_closure_model(closure_model(transitions=(MeshClosureTransition('retry_payment',
            consumes=('root_start',), emits=('payment_result',), consumer_model_id='payment', loop=True,
            max_iterations=3),), joins=(), terminals=(MeshClosureTerminal('payment_done', consumes=('payment_result',
            )),), required_outputs=('payment_result',)))
        self.assertTrue(report.ok)

    def test_parent_invariant_consumes_closure_before_green(self):
        mesh = closure_model(required_outputs=('payment_result', 'inventory_result'),
            transitions=(MeshClosureTransition('start_payment', consumes=('root_start',), emits=('payment_result',)),
            ), joins=(), terminals=(MeshClosureTerminal('payment_done', consumes=('payment_result',)),))
        report = parent_model(mesh).explore()
        self.assertFalse(report.ok)
        self.assertEqual('handoffs_close', report.violations[0].invariant_name)
        self.assertIn('unconsumed_child_output', report.violations[0].message)

    def test_parent_invariant_is_green_when_handoffs_close(self):
        mesh = closure_model(required_outputs=('payment_result', 'inventory_result'))
        closure = review_mesh_closure_model(mesh)
        self.assertTrue(closure.ok)
        self.assertEqual('mesh_closure_green', closure.decision)
        report = parent_model(mesh).explore()
        self.assertTrue(report.ok, report.format_text())

    def test_explicit_closure_is_checked_even_without_a_handoff(self):
        mesh = MeshClosureModel('parent', root_entries=('start',), terminals=(MeshClosureTerminal('done',
            consumes=('start',)),))
        self.assertTrue(review_mesh_closure_model(mesh).ok)
        invalid = review_mesh_closure_model(replace(mesh, terminals=()))
        self.assertFalse(invalid.ok)
        self.assertIn('unreachable_normal_exit', [finding.code for finding in invalid.findings])
        outside = replace(mesh, require_normal_exit=False, terminals=(MeshClosureTerminal('outside', consumes=('start',
            ), terminal_kind=MESH_CLOSURE_OUT_OF_SCOPE),))
        self.assertTrue(review_mesh_closure_model(outside).ok)
        self.assertFalse(review_mesh_closure_model(replace(outside, require_normal_exit=True)).ok)

def test_closure_invariant_fails_a_parent_model_with_an_unconsumed_output():
    mesh = MeshClosureModel('parent', root_entries=('start',), required_outputs=('handoff',),
        transitions=(MeshClosureTransition('produce', consumes=('start',), emits=('handoff',)),),
        terminals=(MeshClosureTerminal('early', consumes=('start',)),))
    failed = parent_model(mesh).explore()
    assert not failed.ok
    assert failed.violations[0].invariant_name == 'handoffs_close'
    assert 'unconsumed_child_output' in failed.violations[0].message
    closed = replace(mesh, transitions=mesh.transitions + (MeshClosureTransition('consume', consumes=('handoff',),
        emits=('done',)),), terminals=(MeshClosureTerminal('done', consumes=('done',)),))
    passed = parent_model(closed).explore()
    assert passed.ok, passed.format_text()
