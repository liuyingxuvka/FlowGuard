"""Compatibility entrypoint for the canonical self-governance check command."""

from __future__ import annotations

from check_flowguard_self_governance import main


if __name__ == "__main__":
    raise SystemExit(main())
