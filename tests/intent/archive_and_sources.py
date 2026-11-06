"""Keep already-correct request and source boundaries visible to the next session."""
from flowguard.intent import Refused, row, rule
from tests.intent_support import QuoteCase


@rule('PROJECT_CODE', decides='project_code_boundary', fields={'filename': (
    'source', 'empty', 'sibling', 'environment', 'site_packages', 'interpreter', 'ordinary_dot_directory', 'relative')},
    source='doc docs/intent-contracts.md "Project-owned code is inside the project"')
def PROJECT_CODE(filename):
    """An environment under the project must never become application code again."""
    if filename in ('source', 'ordinary_dot_directory'):
        return True
    if filename in ('empty', 'sibling', 'environment', 'site_packages', 'interpreter', 'relative'):
        return False
    return None


PROJECT_CODE.rows(
    row(filename='source', expect=True, why='ordinary source remains visible'),
    row(filename='environment', expect=False, why='R33: nested numpy was mistaken for project code'),
    row(filename='sibling', expect=False, why='a shared path prefix is not containment'),
    row(filename='site_packages', expect=False, why='dependency ownership is independent of its location'),
    row(filename='interpreter', expect=False, why='the interpreter is not project code even without a pyvenv marker'),
    row(filename='relative', expect=False, why='a relative frame filename is outside the absolute lexical boundary'),
    row(filename='ordinary_dot_directory', expect=True, why='a directory name alone is not a virtual environment'))




@rule('QUOTE_WORDS', decides='quote_word_identity', fields={'quote': QuoteCase},
    source='doc docs/intent-contracts.md "Owner-word and document quotes use the same whitespace-and-elision comparison."')
def QUOTE_WORDS(quote):
    """The request archive and document authority must agree on the same quote."""
    if quote in (QuoteCase.EXACT, QuoteCase.WHITESPACE, QuoteCase.ELISION):
        return True
    return False


QUOTE_WORDS.rows(
    row(quote=QuoteCase.EXACT, expect=True, why='exact words'),
    row(quote=QuoteCase.WHITESPACE, expect=True, why='whitespace layout is not a word change'),
    row(quote=QuoteCase.ELISION, expect=True, why='ordered elision'),
    row(quote=QuoteCase.REVERSED, expect=False, why='word order must not be forgotten'),
    row(quote=QuoteCase.CHANGED, expect=False, why='a changed word is not an original'),
    row(quote=QuoteCase.ONLY_ELISION, expect=False, why='empty fragments are not evidence'))






@rule('REQUEST_BYTES', decides='immutable_owner_bytes', fields={'exists': bool, 'payload': str},
    source='doc docs/intent-contracts.md "A nonempty UTF-8 owner request is saved byte for byte once."')
def REQUEST_BYTES(exists, payload):
    """Both entry points keep exact bytes and refuse a second write."""
    if payload == '':
        return None
    if exists:
        return Refused('MapError')
    return payload


REQUEST_BYTES.rows(
    row(exists=False, payload='原话不加换行', expect='原话不加换行', why='retain every UTF-8 byte without adding a newline'),
    row(exists=False, payload='line one\r\nline two\n', expect='line one\r\nline two\n', why='line endings are owner bytes'),
    row(exists=True, payload='changed words', expect=Refused('MapError'), why='later sessions cannot rewrite an original'))


@rule('INTENT_SENTINEL', decides='complete_intent_collection', fields={'loaded': bool, 'complete': bool},
    source='doc docs/intent-contracts.md "The collection sentinel succeeds only with the plugin loaded and every declared item collected or validly reused."')
def INTENT_SENTINEL(loaded, complete):
    """A missing plugin or missing intent item must fail visibly."""
    if loaded and complete:
        return True
    return Refused('AssertionError')


INTENT_SENTINEL.rows(
    row(loaded=True, complete=True, expect=True, why='ordinary complete collection'),
    row(loaded=False, complete=True, expect=Refused('AssertionError'), why='zero collected items cannot masquerade as success'),
    row(loaded=True, complete=False, expect=Refused('AssertionError'), why='ignoring the intent directory loses its guards'))
