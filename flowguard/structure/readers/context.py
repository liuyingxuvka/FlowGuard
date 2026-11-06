"""Project parser inputs: content identities, not compiler execution or a new config format."""
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
import json
from flowguard.map.common import content_digest
from .common import GRAMMARS


def config_files(files):
    return sorted(p for p in files if Path(p).name in ('compile_commands.json', 'compile_flags.txt', 'CMakeLists.txt')
                  or Path(p).name.startswith(('tsconfig', 'jsconfig')) and p.endswith('.json')
                  or p.endswith(('.csproj', '.props', '.targets')))


def context_digest(root, files):
    packages = {'tree-sitter', *(item[1] for item in GRAMMARS.values())}
    versions = {}
    for name in packages:
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = 'not installed'
    inputs = {path: content_digest(root / path) for path in config_files(files)}
    return content_digest(Path(__file__), data=json.dumps([versions, inputs], sort_keys=True).encode())


def typescript_paths(root, importer):
    """The closest JSON ts/jsconfig's explicit paths. Unsupported JSONC/extends stays unknown."""
    folder = (root / importer).parent
    while folder.is_relative_to(root):
        for name in ('tsconfig.json', 'jsconfig.json'):
            path = folder / name
            if path.is_file():
                try:
                    data = json.loads(path.read_text(encoding='utf-8-sig'))
                except (ValueError, OSError):
                    return [], 'project config is not readable strict JSON'
                if 'extends' in data:
                    return [], 'extended TypeScript configuration requires project semantic context'
                opts = data.get('compilerOptions', {})
                base = (folder / opts.get('baseUrl', '.')).resolve()
                if not base.is_relative_to(root):
                    return [], 'configured baseUrl is outside mapped roots'
                rows = [(key, target) for key, values in opts.get('paths', {}).items()
                        if isinstance(values, list) for target in values if isinstance(target, str)]
                return [(key, base.relative_to(root).as_posix(), target) for key, target in rows], ''
        if folder == root:
            break
        folder = folder.parent
    return [], ''
