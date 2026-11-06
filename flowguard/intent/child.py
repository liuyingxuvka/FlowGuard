"""Follow Python child functions, without collecting arguments, results or I/O."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import sys


def start():
    root = os.environ.get('FLOWGUARD_TRACE_ROOT')
    folder = os.environ.get('FLOWGUARD_TRACE_CHILDREN')
    test = os.environ.get('FLOWGUARD_TRACE_TEST')
    imports = os.environ.get('FLOWGUARD_IMPORT_ROOT') or root
    if imports:
        from .imports import prepare
        prepare(imports)
    if not root or not folder or not test:
        return
    from .config import load_config, project_code
    from .tracer import Footprint
    footprint = Footprint(project_code(load_config(root)))
    failure = {}
    previous_hook = sys.excepthook

    def exception(kind, value, traceback):
        failure.update(type=kind.__name__, name=getattr(value, 'name', '') or '',
                       filename=os.fsdecode(getattr(value, 'filename', '') or ''))
        previous_hook(kind, value, traceback)

    def finish():
        footprint.__exit__()
        path = Path(folder) / (str(os.getpid()) + '.json')
        path.write_text(json.dumps(dict(test=test, entered=sorted(footprint.entered), edges=sorted(footprint.edges),
                                        call_lines=sorted(footprint.call_lines), failure=failure)), encoding='utf-8')

    footprint.__enter__()
    sys.excepthook = exception
    atexit.register(finish)
