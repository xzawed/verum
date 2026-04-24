#!/usr/bin/env python3
"""Stub hook — delegates to project root hook or exits cleanly.

This file exists because the Claude Code hook runner resolves relative paths
from the edited file's directory. The real hook lives at the repo root.
"""
import os
import subprocess
import sys


def main() -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(0)
    main_repo = os.path.dirname(result.stdout.strip())
    real_hook = os.path.join(main_repo, ".claude", "hooks", "post_test_edit.py")
    if not os.path.exists(real_hook):
        sys.exit(0)
    stdin_data = sys.stdin.buffer.read()
    r = subprocess.run([sys.executable, real_hook], input=stdin_data)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
