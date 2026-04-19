"""FastAPI dependency: resolve current user from headers set by the trusted
Next.js proxy. FastAPI is only reachable on Railway's internal network, so
the proxy is the only legitimate caller; the shared INTERNAL token enforces this."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.users import User
from src.db.session import get_db


def _expected_token() -> str:
    token = os.environ.get("VERUM_INTERNAL_API_TOKEN")
    if not token:
        raise HTTPException(500, "VERUM_INTERNAL_API_TOKEN not configured on API")
    return token


async def get_current_user(
    x_verum_internal_token: Annotated[str | None, Header()] = None,
    x_verum_user_id: Annotated[str | None, Header()] = None,
    x_verum_user_login: Annotated[str | None, Header()] = None,
    x_verum_user_email: Annotated[str | None, Header()] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = ...,  # type: ignore[assignment]
) -> User:
    if x_verum_internal_token != _expected_token():
        raise HTTPException(401, "Invalid or missing internal token")
    if not x_verum_user_id or not x_verum_user_id.isdigit():
        raise HTTPException(401, "Missing user identity")

    github_id = int(x_verum_user_id)
    user = (
        await db.execute(select(User).where(User.github_id == github_id))
    ).scalar_one_or_none()

    now = datetime.now(tz=timezone.utc)
    if user is None:
        user = User(
            id=uuid.uuid4(),
            github_id=github_id,
            github_login=x_verum_user_login or f"user-{github_id}",
            email=x_verum_user_email or None,
            avatar_url=None,
            last_login_at=now,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.last_login_at = now
        await db.commit()

    return user
