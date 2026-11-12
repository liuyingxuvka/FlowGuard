"""Removal notices for supported spellings and features retained until 5.0.

A notice goes to stderr, once per feature in a process: a run that reads a deprecated spelling in a hundred files
says so once. Every use is remembered (`USED`), so a run can name the deprecated features it used (`show --last`)
also when an earlier run of the same process already printed their notice. A run whose own output would hide its
notices (pytest's collection captures stderr; vitest runs FlowGuard in subprocesses whose stderr no one reads)
holds them (`held`, `hold`) and prints them once at its end, on stderr after its block (design 4.7, `say`)."""
from __future__ import annotations

from contextlib import contextmanager
import sys

SAID = set()        # the features whose notice this process printed or a holder took
USED = []           # every use of a deprecated feature in this process, in order
HOLDERS = []        # the lists that take new notices instead of stderr (`hold`), the innermost last


def warn(feature, replacement=None):
    """`deprecated: {feature} goes in 5.0 -> write {replacement}` (design 4.7; `-> do not use it` without one)."""
    USED.append(feature)
    if feature in SAID:
        return
    SAID.add(feature)
    notice = f'deprecated: {feature} goes in 5.0 -> ' + (f'write {replacement}' if replacement else 'do not use it')
    if HOLDERS:
        HOLDERS[-1].append(notice)
    else:
        print(notice, file=sys.stderr)


def hold(notices):
    """From now on the list `notices` takes this process's new notices instead of stderr, until `unhold(notices)`."""
    HOLDERS.append(notices)
    return notices


def unhold(notices):
    """`notices` takes no more notices (it keeps those it took); nothing when it holds none."""
    HOLDERS[:] = [holder for holder in HOLDERS if holder is not notices]


@contextmanager
def held():
    """A list that takes the notices of the block it runs, which then print where its run says them (`say`)."""
    notices = hold([])
    try:
        yield notices
    finally:
        unhold(notices)


def say(notices):
    """Print held notices on stderr, each once, after a run's block; `notices` is emptied."""
    lines = list(dict.fromkeys(notices))
    notices.clear()
    if lines:
        print('\n'.join(lines), file=sys.stderr)


def mark():
    """Where a run starts in `USED`: `used(mark())` at its end names what it used."""
    return len(USED)


def used(since=0):
    """The deprecated features used since `since` (a `mark`), each once, in the order of their first use."""
    return list(dict.fromkeys(USED[since:]))
