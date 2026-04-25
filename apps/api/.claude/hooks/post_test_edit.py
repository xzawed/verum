#!/usr/bin/env python3
"""Proxy hook — delegates to repo-root hook regardless of CWD.

Path depth: apps/api/.claude/hooks/post_test_edit.py
            ^5   ^4   ^3      ^2    ^1 (abspath)
5x dirname -> repo root
"""
import sys
import os

_here = os.path.abspath(__file__)
root = _here
for _ in range(5):
    root = os.path.dirname(root)

real_hook = os.path.join(root, ".claude", "hooks", "post_test_edit.py")

if os.path.exists(real_hook):
    with open(real_hook, "r", encoding="utf-8") as f:
        exec(compile(f.read(), real_hook, "exec"), {"__file__": real_hook})
sys.exit(0)
