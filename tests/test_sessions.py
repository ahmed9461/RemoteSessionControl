from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.sessions import ACTIVE, REVOKED, activate_with_pairing, create_session, remaining_seconds, revoke_session, validate_reconnect_token


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def test_session_clock_starts_at_activation(db):
    row, code = create_session(db, 3600)
    created = aware(row.created_at)
    assert row.activated_at is None
    assert row.expires_at is None

    activation = activate_with_pairing(
        db,
        code,
        {"instance_id": "test-device-1", "name": "Laptop", "platform": "Windows"},
    )
    activated = aware(activation.session.activated_at)
    expires = aware(activation.session.expires_at)
    assert activation.session.status == ACTIVE
    assert activated >= created
    assert 3598 <= int((expires - activated).total_seconds()) <= 3600
    assert 3590 <= remaining_seconds(activation.session) <= 3600


def test_pairing_code_is_single_use(db):
    _, code = create_session(db, 600)
    activate_with_pairing(db, code, {"instance_id": "test-device-2", "name": "PC", "platform": "Windows"})
    with pytest.raises(ValueError, match="invalid pairing code"):
        activate_with_pairing(db, code, {"instance_id": "other", "name": "Other", "platform": "Windows"})


def test_reconnect_token_is_session_bound(db):
    _, code = create_session(db, 600)
    activation = activate_with_pairing(db, code, {"instance_id": "test-device-3", "name": "Mac", "platform": "Darwin"})
    found = validate_reconnect_token(db, activation.reconnect_token)
    assert found.id == activation.session.id

    revoke_session(db, activation.session)
    assert activation.session.status == REVOKED
    with pytest.raises(ValueError, match="not active"):
        validate_reconnect_token(db, activation.reconnect_token)


def test_same_device_cannot_start_second_live_session(db):
    _, first_code = create_session(db, 600)
    activate_with_pairing(db, first_code, {"instance_id": "stable-id", "name": "PC", "platform": "Windows"})
    _, second_code = create_session(db, 600)
    with pytest.raises(ValueError, match="already has an active session"):
        activate_with_pairing(db, second_code, {"instance_id": "stable-id", "name": "PC", "platform": "Windows"})
