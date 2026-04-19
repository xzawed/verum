"""FastAPI dependency: resolve current authenticated user from Bearer token."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.users import User
from src.db.session import get_db
from .jwt_verifier import TokenVerificationError, verify_token


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = ...,  # type: ignore[assignment]
) -> User:
    """Extract JWT from Authorization header, verify, and upsert the user row.

    On first login the user is created automatically. Subsequent calls update
    last_login_at. Raises 401 on any auth failure.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = verify_token(token)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    github_id = int(claims.sub)
    user = (
        await db.execute(select(User).where(User.github_id == github_id))
    ).scalar_one_or_none()

    now = datetime.now(tz=timezone.utc)
    if user is None:
        user = User(
            id=uuid.uuid4(),
            github_id=github_id,
            github_login=claims.github_login or claims.name or f"user-{github_id}",
            email=claims.email,
            avatar_url=claims.picture,
            last_login_at=now,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.last_login_at = now
        await db.commit()

    return user
