"""FlowGuard Map: the project's living, code-anchored information map ("DNA") and proof models.

Files in a target project:
  .flowguard/map.json        components, responsibilities, files, deps, tests, models (commit it)
  .flowguard/models/*.py     executable models of risky flows (commit them)
  .flowguard/cache/          parse caches (never commit; safe to delete)

Run ``python -m flowguard.map --help`` for commands.
"""

from .cli import main

__all__ = ["main"]
