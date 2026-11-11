"""Removal notices for supported spellings and features retained until 5.0."""
from __future__ import annotations

import sys


def warn(feature, replacement=None):
    message = f'deprecated: {feature} will be removed in 5.0'
    if replacement:
        message += '; write ' + replacement
    print(message, file=sys.stderr)
