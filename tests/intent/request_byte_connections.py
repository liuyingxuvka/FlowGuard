"""The same original byte rule observes two actual native scenarios."""
from flowguard.intent import flow, Node, Read, Relation


flow('RECORD_BYTES_OBSERVATION',
     source='doc docs/intent-contracts.md "A nonempty UTF-8 owner request is saved byte for byte once."',
     nodes=[Node('case', 'RECORD_CASE'), Node('write', 'RECORD_WRITE', caller='case'),
            Node('refused', 'RECORD_WRITE', phase='raise', caller='case'),
            Node('reading', 'ORIGINAL_BYTES', phase='return', caller='case'),
            Node('read_error', 'ORIGINAL_BYTES', phase='raise', caller='case'),
            Node('done', 'RECORD_CASE', phase='return')],
     edges=[('case', 'write'), ('write', 'refused'), ('refused', 'done'),
            ('write', 'reading'), ('write', 'read_error'),
            ('reading', 'done'), ('read_error', 'done')],
     relations=[Relation('REQUEST_BYTES', {'exists': Read('case', 'arg.exists'), 'payload': Read('case', 'arg.payload')},
                         Read('reading', view='utf8'), on='reading'),
                Relation('REQUEST_BYTES', {'exists': Read('case', 'arg.exists'), 'payload': Read('case', 'arg.payload')},
                         Read('refused', 'error'), on='refused'),
                Relation('REQUEST_BYTES', {'exists': Read('case', 'arg.exists'), 'payload': Read('case', 'arg.payload')},
                         Read('read_error', 'error'), on='read_error')])


flow('REQUEST_BYTES_OBSERVATION',
     source='doc docs/intent-contracts.md "A nonempty UTF-8 owner request is saved byte for byte once."',
     nodes=[Node('case', 'REQUEST_CASE'), Node('write', 'REQUEST_STORE', caller='case'),
            Node('refused', 'REQUEST_STORE', phase='raise', caller='case'),
            Node('metadata', 'REQUEST_METADATA', phase='return', caller='case'),
            Node('metadata_error', 'REQUEST_METADATA', phase='raise', caller='case'),
            Node('reading', 'REQUEST_BODY', phase='return', caller='case'),
            Node('read_error', 'REQUEST_BODY', phase='raise', caller='case'),
            Node('done', 'REQUEST_CASE', phase='return')],
     edges=[('case', 'write'), ('write', 'refused'), ('refused', 'done'),
            ('write', 'metadata'), ('write', 'metadata_error'), ('metadata_error', 'done'),
            ('metadata', 'reading'), ('metadata', 'read_error'),
            ('reading', 'done'), ('read_error', 'done')],
     relations=[Relation('REQUEST_BYTES', {'exists': Read('case', 'arg.exists'), 'payload': Read('case', 'arg.payload')},
                         Read('reading', view='utf8'), on='reading'),
                Relation('REQUEST_BYTES', {'exists': Read('case', 'arg.exists'), 'payload': Read('case', 'arg.payload')},
                         Read('refused', 'error'), on='refused'),
                Relation('REQUEST_BYTES', {'exists': Read('case', 'arg.exists'), 'payload': Read('case', 'arg.payload')},
                         Read('metadata_error', 'error'), on='metadata_error'),
                Relation('REQUEST_BYTES', {'exists': Read('case', 'arg.exists'), 'payload': Read('case', 'arg.payload')},
                         Read('read_error', 'error'), on='read_error')])
