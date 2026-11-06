"""Language selection and delivery metadata; no grammar is imported here."""
from pathlib import Path

SUFFIXES = {
    '.py':'python', '.js':'javascript', '.jsx':'javascript', '.mjs':'javascript', '.cjs':'javascript',
    '.ts':'typescript', '.mts':'typescript', '.cts':'typescript', '.tsx':'tsx',
    '.c':'c', '.h':'c', '.cpp':'cpp', '.cc':'cpp', '.cxx':'cpp', '.hpp':'cpp', '.hh':'cpp', '.hxx':'cpp',
    '.cs':'csharp',
}
OTHER_SOURCE = {'.go', '.rs', '.java', '.kt', '.swift', '.m', '.rb', '.php'}


def language_for(path):
    suffix = Path(path).suffix
    return 'cpp' if suffix == '.C' else SUFFIXES.get(suffix.lower())


def module_name(rel):
    return language_for(rel) + '/' + rel


def extract(root, rel, data, module, is_test):
    language = language_for(rel)
    if language in ('javascript', 'typescript', 'tsx'):
        from .ecma import extract as read
    elif language in ('c', 'cpp'):
        from .cfamily import extract as read
    elif language == 'csharp':
        from .csharp import extract as read
    else:
        raise ValueError('no source reader for ' + rel)
    return read(root, rel, data, module, is_test)


def available():
    """Installed delivery, without importing any foreign parser or grammar."""
    from importlib.metadata import version, PackageNotFoundError
    from .common import GRAMMARS
    result = {'python': dict(installed=True, grammar='stdlib ast', native_home=True, suffixes=['.py'], queries=query_support('python'))}
    for language, (_, package, _) in GRAMMARS.items():
        try:
            installed = version(package)
        except PackageNotFoundError:
            installed = None
        reader = 'ecma' if language in ('javascript','typescript','tsx') else 'cfamily' if language in ('c','cpp') else 'csharp'
        result[language] = dict(queries=query_support(language), installed=installed is not None and Path(__file__).with_name(reader+'.py').is_file(),
            grammar=package, grammar_version=installed, native_home=False,
            suffixes=sorted(suffix for suffix, value in SUFFIXES.items() if value == language))
    return result


QUERIES = ('nodes','functions','keys','handlers','literal_sets','assignments','calls','symbol_reads','imports','tests')


def query_support(language):
    """A grammar's existence never grants unimplemented fixed-query coverage."""
    return {name: language == 'python' or language in SUFFIXES.values() and name in ('nodes','functions','keys','assignments','calls','imports')
            for name in QUERIES}
