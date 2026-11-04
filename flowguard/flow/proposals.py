"""The same short setting proposal in check, status and release."""
from __future__ import annotations


def proposal_text(proposal: dict) -> str:
    """Format model.setting_proposals() metadata, optionally with its model ID."""
    model = f"{proposal['model']}: " if proposal.get("model") else ""
    return (f"proposed setting {model}{proposal['name']}={proposal['value']!r}; "
            f"code {proposal['code_value']!r} at {proposal['where']}; {proposal['source']}")
