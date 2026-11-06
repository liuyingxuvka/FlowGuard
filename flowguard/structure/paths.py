"""The single boundary for project-owned Python code."""

import os
import sys
from pathlib import Path

def project_code(filename, root):
    """Only project-owned source, excluding interpreter and dependency environments.

    Callers cache this per native session: the source tree is fixed for that session,
    and trace/profile callbacks must not repeat filesystem probes on every line.
    Keep the lexical root boundary used by source-relative frame locations.
    """
    if not filename or not os.path.normcase(filename).startswith(os.path.normcase(str(root).rstrip(os.sep) + os.sep)):
        return False
    path = Path(filename).resolve()
    project = Path(root).resolve()
    if not path.is_relative_to(project) or path.is_relative_to(Path(sys.prefix).resolve()):
        return False
    if any(os.path.normcase(part) == os.path.normcase('site-packages') for part in path.parts):
        return False
    parent = path.parent
    while parent.is_relative_to(project):
        if (parent / 'pyvenv.cfg').is_file():
            return False
        if parent == project:
            break
        parent = parent.parent
    return True
