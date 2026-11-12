"""Removal notices for supported spellings and features retained until 5.0.

A notice goes to stderr, once per feature in a process: a run that reads a deprecated spelling in a hundred files
says so once. Every use is remembered (`USED`), so a run can name the deprecated features it used (`show --last`)
also when an earlier run of the same process already printed their notice."""
from __future__ import annotations

import sys

SAID = set()        # the features whose notice this process printed
USED = []           # every use of a deprecated feature in this process, in order


def warn(feature, replacement=None):
    """`deprecated: {feature} goes in 5.0 -> write {replacement}` (design 4.7; `-> do not use it` without one)."""
    USED.append(feature)
    if feature in SAID:
        return
    SAID.add(feature)
    print(f'deprecated: {feature} goes in 5.0 -> ' + (f'write {replacement}' if replacement else 'do not use it'), file=sys.stderr)


def mark():
    """Where a run starts in `USED`: `used(mark())` at its end names what it used."""
    return len(USED)


def used(since=0):
    """The deprecated features used since `since` (a `mark`), each once, in the order of their first use."""
    return list(dict.fromkeys(USED[since:]))
