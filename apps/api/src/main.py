"""Worker entrypoint — delegates to the asyncio job loop.

Node.js spawns this module as a child process: `python -m src.main`
"""
import asyncio
import logging

from src.worker.runner import run_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [worker] %(name)s %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    asyncio.run(run_loop())
