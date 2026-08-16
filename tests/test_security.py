from __future__ import annotations

from core.security import generate_pairing_code, generate_reconnect_token, token_hash


def test_pairing_code_shape():
    code = generate_pairing_code()
    left, right = code.split("-")
    assert len(left) == 4
    assert len(right) == 4


def test_tokens_are_hashed_and_random():
    one = generate_reconnect_token()
    two = generate_reconnect_token()
    assert one != two
    assert token_hash(one) != one
    assert token_hash(one) == token_hash(one)
