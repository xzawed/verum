"""Python worker entrypoint — asyncio job loop.

Node.js spawns this as a child process at container startup.
It claims and runs verum_jobs via Postgres SKIP LOCKED + LISTEN/NOTIFY.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from .runner import run_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [worker] %(name)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

if __name__ == "__main__":
    asyncio.run(run_loop())
