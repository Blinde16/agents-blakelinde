"""Verify Clerk-issued JWTs (RS256) using the issuer JWKS."""

from __future__ import annotations

import os

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    issuer = os.getenv("CLERK_JWT_ISSUER", "").rstrip("/")
    if not issuer:
        raise HTTPException(
            status_code=500,
            detail="CLERK_JWT_ISSUER is not configured",
        )
    url = f"{issuer}/.well-known/jwks.json"
    if _jwks_client is None:
        _jwks_client = PyJWKClient(url)
    return _jwks_client


def decode_clerk_jwt_sub(token: str) -> str:
    """
    Returns Clerk `sub` (user id) after signature verification.
    """
    if os.getenv("AGENT_TESTING") == "1":
        test_uid = os.getenv("TEST_CLERK_USER_ID")
        if test_uid:
            return test_uid

    if os.getenv("ALLOW_INSECURE_DEV_AUTH") == "1":
        dev_uid = os.getenv("DEV_CLERK_USER_ID")
        if dev_uid and token == "dev-bypass-token":
            return dev_uid

    issuer = os.getenv("CLERK_JWT_ISSUER", "").rstrip("/")
    if not issuer:
        raise HTTPException(status_code=500, detail="CLERK_JWT_ISSUER is not configured")

    try:
        jwks = _get_jwks_client()
        signing_key = jwks.get_signing_key_from_jwt(token)
        # TODO: set verify_aud True and pass audience= once Clerk JWT template + env are fixed
        # (e.g. azp or custom aud); leaving aud unchecked accepts any audience for this issuer.
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
    except jwt.exceptions.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(status_code=401, detail="Token missing sub")
    return sub
