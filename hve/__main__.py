"""Allow ``python -m hve`` to invoke the HVE CLI."""

from .cli import main
import sys
import os

if __name__ == "__main__":
    # Resolve the HVE home directory from the active runtime environment.
    # before running. The CLI reads this on every command.
    sys.exit(main())
