from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, Header, HTTPException

from src.api.clerk_jwt import decode_clerk_jwt_sub


async def verify_internal_token(x_service_token: str = Header(...)) -> str:
    """
    Validates that requests are originating from the Next.js frontend
    by checking the internal signed service token.
    """
    expected_token = os.getenv("INTERNAL_SERVICE_KEY_SIGNER", "dev_service_token_123")

    if x_service_token != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid internal service token")

    return x_service_token


async def require_bearer_clerk_sub(
    authorization: Optional[str] = Header(None),
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization Bearer token required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")
    return decode_clerk_jwt_sub(token)


async def authenticate_internal(
    _: str = Depends(verify_internal_token),
    clerk_sub: str = Depends(require_bearer_clerk_sub),
) -> str:
    """Validates internal service token + Clerk JWT; returns Clerk `sub`."""
    return clerk_sub
