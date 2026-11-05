"""FlowGuard models, native replay records and source tools; one executable model engine."""

from __future__ import annotations

import importlib
from typing import Any

__version__ = "1.2.0"

# owner module -> public names
_PUBLIC_API: dict[str, tuple[str, ...]] = {'flowguard.conformance': ('ConformanceReport',
                           'ConformanceRule',
                           'ConformanceViolation',
                           'default_conformance_rules',
                           'projected_output_matches',
                           'projected_state_matches',
                           'replay_trace',
                           'select_covering_traces'),
 'flowguard.export': ('to_json_text', 'to_jsonable'),
 'flowguard.replay': ('ReplayAdapter', 'ReplayObservation'),
 'flowguard.templates': ('TemplateFile', 'adoption_template_files', 'write_template_files'),
 'flowguard.trace': ('Trace', 'TraceStep')}

_OWNER: dict[str, str] = {name: owner for owner, group in _PUBLIC_API.items() for name in group}
__all__ = sorted(_OWNER)


def __getattr__(name: str) -> Any:
    owner = _OWNER.get(name)
    if owner is None:
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name != f"{__name__}.{name}":
                raise
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
        globals()[name] = module
        return module
    value = getattr(importlib.import_module(owner), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
