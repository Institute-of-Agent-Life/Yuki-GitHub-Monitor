"""Stopped-database diagnostics, outside the runtime plugin lifecycle."""

from github_monitor.doctor import main

if __name__ == "__main__":
    raise SystemExit(main())
