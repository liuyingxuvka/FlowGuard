"""One literal-expression decision shared by the direct and source-file readers."""
from flowguard.intent import row, rule


@rule('ROW_LITERALS', decides='row_expression_literal', fields={'expression': str,
    'spelling': ('direct', 'alias', 'module', 'helper')},
    source='doc docs/intent-contracts.md "Row expressions contain literals rather than globals, arithmetic or helper calls."')
def ROW_LITERALS(expression, spelling):
    """An alias must not allow computed or borrowed case values."""
    if spelling not in ('direct', 'alias', 'module', 'helper'):
        return None
    if expression in ('1', '[1, None, True]', "D('1.25')", 'date(2026, 11, 5)'):
        return True
    if expression in ('GLOBAL', '1 + 3', 'make_value()'):
        return False
    return None


ROW_LITERALS.rows(
    row(expression='1', spelling='direct', expect=True, why='a literal case remains cheap to write'),
    row(expression='[1, None, True]', spelling='alias', expect=True, why='the alias changes no input meaning'),
    row(expression="D('1.25')", spelling='module', expect=True, why='decimal text keeps its precision'),
    row(expression='GLOBAL', spelling='alias', expect=False, why='an alias must not borrow mutable code values'),
    row(expression='1 + 3', spelling='direct', expect=False, why='rows retain literal regressions rather than recomputing them'),
    row(expression='GLOBAL', spelling='helper', expect=False, why='a helper body does not hide a borrowed input'),
    row(expression='make_value()', spelling='module', expect=False, why='helpers cannot replace the case values'))
