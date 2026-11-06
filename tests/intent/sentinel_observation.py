"""The sentinel's None return is not its success reading."""
from flowguard.intent import flow, Node, Read, Relation

flow('SENTINEL_OBSERVATION',
     source='doc docs/intent-contracts.md "The collection sentinel succeeds only with the plugin loaded and every declared item collected or validly reused."',
     nodes=[Node('case', 'SENTINEL_CASE'),
            Node('returned', 'SENTINEL_CHECK', phase='return'),
            Node('failed', 'SENTINEL_CHECK', phase='raise'),
            Node('done', 'SENTINEL_CASE', phase='return')],
     edges=[('case', 'returned'), ('returned', 'done'),
            ('case', 'failed'), ('failed', 'done')],
     relations=[Relation('INTENT_SENTINEL',
                         {'loaded': Read('case', 'arg.loaded'), 'complete': Read('case', 'arg.complete')},
                         Read('returned', 'state.Session.sentinel', equals='ok'), on='returned'),
                Relation('INTENT_SENTINEL',
                         {'loaded': Read('case', 'arg.loaded'), 'complete': Read('case', 'arg.complete')},
                         Read('failed', 'error'), on='failed')])
