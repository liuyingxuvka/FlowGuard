"""The single boundary for project-owned Python code."""

import os
import sys
from pathlib import Path

# flowguard: sensor PROJECT_SOURCE(filename: path, root: path) -> accepted: bool calibrated_by=tests/test_anchor_self_rules.py::test_project_anchor_case[source]
def project_code(filename: str, root: Path) -> bool:
    """Only project-owned source, excluding interpreter and dependency environments.

    Callers cache this per native session: the source tree is fixed for that session,
    and trace/profile callbacks must not repeat filesystem probes on every line.
    Keep the lexical root boundary used by source-relative frame locations.
    """
    if not _lexical(filename, root):
        return False
    return _accepted(filename, Path(root).resolve(), Path(sys.prefix).resolve(), {}, None)


def project_files(filenames, root: Path) -> list[bool]:
    """project_code of each file of one listing (a map build), in order. The root, the interpreter prefix,
    each directory's real path and each directory's environment check are resolved once for the listing,
    not once per file."""
    project, prefix = Path(root).resolve(), Path(sys.prefix).resolve()
    environments, directories = {}, {} if os.name == 'posix' else None
    return [_lexical(filename, root) and _accepted(filename, project, prefix, environments, directories)
            for filename in filenames]


def _lexical(filename, root):
    """The cheap first test: the file's spelling starts inside the root (most files asked are not)."""
    return bool(filename) and os.path.normcase(filename).startswith(os.path.normcase(str(root).rstrip(os.sep) + os.sep))


def _resolved(filename, directories):
    """Path(filename).resolve(); with `directories`, the folder's real path is resolved once per listing
    (POSIX: the real path of folder/name is the folder's real path joined with name, unless name is a link)."""
    head, name = os.path.split(filename)
    if directories is None or not head or name in ('', '.', '..'):
        return Path(filename).resolve()
    folder = directories.get(head)
    if folder is None:
        folder = directories[head] = Path(head).resolve()
    path = folder / name
    return path.resolve() if path.is_symlink() else path


def _accepted(filename, project, prefix, environments, directories):
    path = _resolved(filename, directories)
    if not path.is_relative_to(project) or path.is_relative_to(prefix):
        return False
    if any(os.path.normcase(part) == os.path.normcase('site-packages') for part in path.parts):
        return False
    return not _environment(path.parent, project, environments)


def _environment(directory, project, known):
    """Whether `directory` or a directory above it, up to the project root, holds a pyvenv.cfg.
    `known` keeps the answer of each directory looked at, for the next file of the same listing."""
    passed, found = [], False
    while True:
        if directory in known:
            found = known[directory]
            break
        if not directory.is_relative_to(project):
            break
        passed.append(directory)
        if (directory / 'pyvenv.cfg').is_file():
            found = True
            break
        if directory == project:
            break
        directory = directory.parent
    for seen in passed:
        known[seen] = found
    return found
