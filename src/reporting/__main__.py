"""Expose report tools through ``python -m reporting``."""

from reporting.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
