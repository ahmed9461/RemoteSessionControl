from __future__ import annotations

import hashlib
import hmac
import secrets

from core.config import get_settings

PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_pairing_code() -> str:
    left = "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(4))
    right = "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(4))
    return f"{left}-{right}"


def generate_reconnect_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(value: str) -> str:
    pepper = get_settings().owner_api_key.encode("utf-8")
    return hmac.new(pepper, value.encode("utf-8"), hashlib.sha256).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
