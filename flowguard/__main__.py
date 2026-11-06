"""The single public FlowGuard command entry."""
import sys
from .intent.cli import main as intent_main
from .map.common import quiet_broken_pipe, safe_stdio


def main(argv=None):
    safe_stdio()
    try:
        return quiet_broken_pipe(lambda: intent_main(argv))()
    except KeyboardInterrupt:
        print('flowguard: interrupted', file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
