"""`python -m flowguard._next check|show ...` until the move-in wires the verbs into
`python -m flowguard` (design 7.6)."""
import sys

from .cli import main

sys.exit(main(sys.argv[1:]))
