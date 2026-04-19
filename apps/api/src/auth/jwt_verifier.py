"""Verify Auth.js v5 JWE tokens issued by the Verum dashboard.

Auth.js v5 default JWT encoding:
- Algorithm:  dir (direct key agreement)
- Encryption: A256CBC-HS512
- Key:        64 bytes derived from AUTH_SECRET via HKDF-SHA256,
              info = b"Auth.js Generated Encryption Key"

The dashboard must set AUTH_SECRET; the FastAPI service reads the same
value as NEXTAUTH_SECRET. They must be identical.
"""
from __future__ import annotations

import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from jose import JWEError, jwe
from pydantic import BaseModel, ValidationError


class JwtClaims(BaseModel):
    sub: str  # GitHub numeric user ID as a string
    name: str | None = None
    email: str | None = None
    picture: str | None = None
    github_login: str | None = None


class TokenVerificationError(Exception):
    pass


def _derive_key(secret: str) -> bytes:
    """Derive a 64-byte key from AUTH_SECRET using the same HKDF params as Auth.js v5."""
    return HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=b"",
        info=b"Auth.js Generated Encryption Key",
    ).derive(secret.encode())


def verify_token(token: str) -> JwtClaims:
    """Decrypt and validate an Auth.js v5 JWE session token.

    Raises:
        TokenVerificationError: if NEXTAUTH_SECRET is missing, the token is
            malformed / expired, or the claims don't conform to JwtClaims.
    """
    secret = os.environ.get("NEXTAUTH_SECRET")
    if not secret:
        raise TokenVerificationError("NEXTAUTH_SECRET environment variable is not set")

    try:
        key = _derive_key(secret)
        decrypted: bytes = jwe.decrypt(token, key)
        payload = json.loads(decrypted)
    except JWEError as exc:
        raise TokenVerificationError(f"JWE decryption failed: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise TokenVerificationError(f"Token payload invalid: {exc}") from exc

    try:
        return JwtClaims.model_validate(payload)
    except ValidationError as exc:
        raise TokenVerificationError(f"Token claims invalid: {exc}") from exc
