"""Fernet helpers for integration tokens stored in Postgres."""

from __future__ import annotations

import os

_PLAIN_PREFIX = "plain:"


def encrypt_secret(plain: str) -> str:
    if os.getenv("ALLOW_PLAINTEXT_INTEGRATION_SECRETS") == "1":
        return _PLAIN_PREFIX + plain
    key = os.getenv("SECRETS_FERNET_KEY")
    if not key:
        raise RuntimeError(
            "Set SECRETS_FERNET_KEY (Fernet key) or ALLOW_PLAINTEXT_INTEGRATION_SECRETS=1 for local dev."
        )
    from cryptography.fernet import Fernet

    return Fernet(key.strip().encode()).encrypt(plain.encode()).decode()


def decrypt_secret(blob: str) -> str:
    if blob.startswith(_PLAIN_PREFIX):
        return blob[len(_PLAIN_PREFIX) :]
    key = os.getenv("SECRETS_FERNET_KEY")
    if not key:
        raise RuntimeError("SECRETS_FERNET_KEY required to decrypt stored integration tokens.")
    from cryptography.fernet import Fernet

    return Fernet(key.strip().encode()).decrypt(blob.encode()).decode()
