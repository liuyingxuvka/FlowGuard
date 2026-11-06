"""The existing product rules read actual scoped test observations."""
from flowguard.intent import flow, Node, Read, Relation


flow('PROJECT_OBSERVATION', source='doc docs/intent-contracts.md "Project-owned code is inside the project"',
     nodes=[Node('case', 'PROJECT_CASE'), Node('reading', 'PROJECT_SOURCE', phase='return', caller='case'),
            Node('done', 'PROJECT_CASE', phase='return')],
     edges=[('case', 'reading'), ('reading', 'done')],
     relations=[Relation('PROJECT_CODE', {'filename': Read('case', 'arg.filename')}, Read('reading'), on='reading')])

flow('QUOTE_OBSERVATION', source='doc docs/intent-contracts.md "Owner-word and document quotes use the same whitespace-and-elision comparison."',
     nodes=[Node('case', 'QUOTE_CASE'), Node('reading', 'QUOTE_MATCH', phase='return', caller='case'),
            Node('done', 'QUOTE_CASE', phase='return')],
     edges=[('case', 'reading'), ('reading', 'done')],
     relations=[Relation('QUOTE_WORDS', {'quote': Read('case', 'arg.quote')}, Read('reading'), on='reading')])

flow('AUTHORITY_OBSERVATION', source='doc docs/intent-contracts.md "Owner-word and document quotes use the same whitespace-and-elision comparison."',
     nodes=[Node('case', 'AUTHORITY_CASE'), Node('reading', 'SOURCE_AUTHORITY', phase='return', caller='case'),
            Node('done', 'AUTHORITY_CASE', phase='return')],
     edges=[('case', 'reading'), ('reading', 'done')],
     relations=[Relation('QUOTE_WORDS', {'quote': Read('case', 'arg.quote')}, Read('reading', 'result.0'), on='reading')])

flow('EXPRESSION_OBSERVATION', source='doc docs/intent-contracts.md "Row expressions contain literals rather than globals, arithmetic or helper calls."',
     nodes=[Node('case', 'EXPRESSION_CASE'), Node('reading', 'ROW_LITERAL', phase='return', caller='case'),
            Node('done', 'EXPRESSION_CASE', phase='return')],
     edges=[('case', 'reading'), ('reading', 'done')],
     relations=[Relation('ROW_LITERALS', {'expression': Read('case', 'arg.expression'),
         'spelling': Read('case', 'arg.spelling')}, Read('reading'), on='reading')])

flow('PROGRAM_OBSERVATION', source='doc docs/intent-contracts.md "Row expressions contain literals rather than globals, arithmetic or helper calls."',
     nodes=[Node('case', 'PROGRAM_CASE'), Node('reading', 'ROW_PROBLEMS', phase='return', caller='case'),
            Node('done', 'PROGRAM_CASE', phase='return')],
     edges=[('case', 'reading'), ('reading', 'done')],
     relations=[Relation('ROW_LITERALS', {'expression': Read('case', 'arg.expression'),
         'spelling': Read('case', 'arg.spelling')}, Read('reading', view='empty'), on='reading')])
