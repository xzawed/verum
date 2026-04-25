#!/usr/bin/env python3
"""Proxy hook — delegates to repo-root hook regardless of CWD."""
import sys
import os

root = os.path.dirname(  # apps/api/.claude/hooks -> apps/api/.claude -> apps/api -> repo root
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
real_hook = os.path.join(root, ".claude", "hooks", "post_test_edit.py")

if os.path.exists(real_hook):
    with open(real_hook, "r", encoding="utf-8") as f:
        exec(compile(f.read(), real_hook, "exec"), {"__file__": real_hook})
sys.exit(0)
