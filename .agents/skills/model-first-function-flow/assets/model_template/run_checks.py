"""Run the minimal model_template checks."""

from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    for parent in Path(__file__).resolve().parents:
        if (parent / "flowguard").is_dir():
            sys.path.insert(0, str(parent))
            break

from flowguard import Explorer  # noqa: E402
import model  # noqa: E402


def main() -> int:
    report = Explorer(
        workflow=model.build_workflow(),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=("stored", "rejected_duplicate"),
    ).explore()
    print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
