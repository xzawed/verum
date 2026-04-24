"""DEPLOY job handler.

Payload schema:
  generation_id: str (UUID)
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.loop.deploy.orchestrator import deploy_and_start_experiment

logger = logging.getLogger(__name__)

_VARIANT_FRACTION: float = float(os.environ.get("VERUM_DEPLOY_VARIANT_FRACTION", "0.10"))
if not (0.0 < _VARIANT_FRACTION < 1.0):
    raise RuntimeError(
        f"VERUM_DEPLOY_VARIANT_FRACTION must be in (0, 1), got {_VARIANT_FRACTION}"
    )
_TEST_MODE: bool = os.environ.get("VERUM_TEST_MODE", "") == "1"
_INTEGRATION_STATE_DIR = Path(os.environ.get("INTEGRATION_STATE_DIR", "/integration-state"))


def _write_integration_state(deployment_id: uuid.UUID, api_key: str) -> None:
    """Atomically write deployment_info.json to the shared integration-state volume.

    Used only when VERUM_TEST_MODE=1. Avoids storing the plaintext api_key in the
    DB job result column while still making it available to fake-arcana/test-runner.
    """
    state_dir = _INTEGRATION_STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"deployment_id": str(deployment_id), "api_key": api_key})
    target = state_dir / "deployment_info.json"
    fd, tmp_path = tempfile.mkstemp(dir=state_dir, prefix=".tmp_deploy_info_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(payload)
        os.replace(tmp_path, target)
    except Exception:
        logger.exception("DEPLOY: failed to write integration state, cleaning up %s", tmp_path)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    logger.info("DEPLOY: wrote integration state to %s", target)


async def handle_deploy(
    db: AsyncSession,
    owner_user_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    generation_id = uuid.UUID(payload["generation_id"])
    deployment, experiment_id = await deploy_and_start_experiment(
        db, generation_id, variant_fraction=_VARIANT_FRACTION
    )
    await db.commit()

    logger.info(
        "DEPLOY+EXPERIMENT: deployment_id=%s experiment_id=%s status=%s",
        deployment.deployment_id,
        experiment_id,
        deployment.status,
    )

    if _TEST_MODE:
        # Write api_key to shared volume instead of DB job result to avoid
        # plaintext key storage in verum_jobs.result (P0-2 security fix).
        _write_integration_state(deployment.deployment_id, deployment.api_key)

    return {
        "deployment_id": str(deployment.deployment_id),
        "status": deployment.status,
        "traffic_split": deployment.traffic_split,
    }
