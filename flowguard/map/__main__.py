import sys

from .. import __version__
from .cli import main
from .impact_history import read_git_paths
from .status import show_status_first

show_status_first(sys.argv[1:], __version__, read_git_paths=read_git_paths)
raise SystemExit(main())
