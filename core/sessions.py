from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.audit import audit
from core.config import get_settings
from core.models import Device, SessionRecord
from core.security import generate_pairing_code, generate_reconnect_token, token_hash

CREATED = "CREATED"
WAITING_FOR_DEVICE = "WAITING_FOR_DEVICE"
ACTIVE = "ACTIVE"
EXPIRED = "EXPIRED"
REVOKED = "REVOKED"
FAILED = "FAILED"


@dataclass(slots=True)
class ActivationResult:
    session: SessionRecord
    device: Device
    reconnect_token: str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_session(db: Session, duration_seconds: int) -> tuple[SessionRecord, str]:
    if duration_seconds < 60 or duration_seconds > 24 * 60 * 60:
        raise ValueError("duration_seconds must be between 60 and 86400")

    code = generate_pairing_code()
    now = utcnow()
    record = SessionRecord(
        id=str(uuid4()),
        status=WAITING_FOR_DEVICE,
        pairing_token_hash=token_hash(code),
        pairing_expires_at=now + timedelta(seconds=get_settings().pairing_ttl_seconds),
        requested_duration_seconds=duration_seconds,
        created_at=now,
    )
    db.add(record)
    db.flush()
    audit(db, "session_created", session_id=record.id, details={"duration_seconds": duration_seconds})
    return record, code


def _resolve_device(db: Session, device_info: dict, now: datetime) -> Device:
    instance_id = str(device_info.get("instance_id") or "")[:64] or None
    device = db.scalar(select(Device).where(Device.instance_id == instance_id)) if instance_id else None
    if device is None:
        device = Device(id=str(uuid4()), instance_id=instance_id, name="Unnamed device", platform="unknown")
        db.add(device)
        db.flush()
    elif device.current_session_id:
        old_session = db.get(SessionRecord, device.current_session_id)
        if old_session and old_session.status == ACTIVE:
            old_expiry = _as_utc(old_session.expires_at)
            if old_expiry and old_expiry > now:
                raise ValueError("device already has an active session")
            expire_session(db, old_session, reason="expired_before_new_pairing")

    device.name = str(device_info.get("name") or device.name or "Unnamed device")[:200]
    device.platform = str(device_info.get("platform") or device.platform or "unknown")[:64]
    device.platform_version = str(device_info.get("platform_version") or "")[:200]
    device.client_version = str(device_info.get("client_version") or "0.1.0")[:32]
    device.last_seen = now
    return device


def activate_with_pairing(db: Session, code: str, device_info: dict) -> ActivationResult:
    now = utcnow()
    record = db.scalar(select(SessionRecord).where(SessionRecord.pairing_token_hash == token_hash(code)))
    if record is None or record.status != WAITING_FOR_DEVICE:
        raise ValueError("invalid pairing code")
    if _as_utc(record.pairing_expires_at) <= now:
        record.status = FAILED
        record.disconnect_reason = "pairing_token_expired"
        audit(db, "pairing_failed", session_id=record.id, details={"reason": "expired"})
        raise ValueError("pairing code expired")

    device = _resolve_device(db, device_info, now)
    reconnect_token = generate_reconnect_token()
    record.device_id = device.id
    record.paired_at = now
    record.activated_at = now
    record.expires_at = now + timedelta(seconds=record.requested_duration_seconds)
    record.reconnect_token_hash = token_hash(reconnect_token)
    record.status = ACTIVE
    device.current_session_id = record.id
    audit(db, "pairing_success", session_id=record.id, device_id=device.id)
    return ActivationResult(record, device, reconnect_token)


def validate_reconnect_token(db: Session, reconnect_token: str) -> SessionRecord:
    now = utcnow()
    record = db.scalar(
        select(SessionRecord).where(SessionRecord.reconnect_token_hash == token_hash(reconnect_token))
    )
    if record is None:
        raise ValueError("invalid reconnect token")
    if record.status != ACTIVE:
        raise ValueError("session is not active")
    expires_at = _as_utc(record.expires_at)
    if expires_at is None or expires_at <= now:
        expire_session(db, record, reason="expired_on_reconnect")
        raise ValueError("session expired")
    return record


def expire_session(db: Session, record: SessionRecord, *, reason: str = "expired") -> None:
    if record.status != ACTIVE:
        return
    record.status = EXPIRED
    record.disconnect_reason = reason
    if record.device_id:
        device = db.get(Device, record.device_id)
        if device and device.current_session_id == record.id:
            device.current_session_id = None
    audit(db, "session_expired", session_id=record.id, device_id=record.device_id, details={"reason": reason})


def expire_due_sessions(db: Session) -> list[str]:
    now = utcnow()
    rows = db.scalars(select(SessionRecord).where(SessionRecord.status == ACTIVE)).all()
    expired_devices: list[str] = []
    for record in rows:
        expires_at = _as_utc(record.expires_at)
        if expires_at and expires_at <= now:
            if record.device_id:
                expired_devices.append(record.device_id)
            expire_session(db, record)
    return expired_devices


def revoke_session(db: Session, record: SessionRecord, reason: str = "manual_disconnect") -> None:
    if record.status not in {ACTIVE, WAITING_FOR_DEVICE}:
        return
    record.status = REVOKED
    record.revoked_at = utcnow()
    record.disconnect_reason = reason
    if record.device_id:
        device = db.get(Device, record.device_id)
        if device and device.current_session_id == record.id:
            device.current_session_id = None
    audit(db, "session_revoked", session_id=record.id, device_id=record.device_id, details={"reason": reason})


def active_session_for_device(db: Session, device_id: str) -> SessionRecord | None:
    record = db.scalar(
        select(SessionRecord).where(
            SessionRecord.device_id == device_id,
            SessionRecord.status == ACTIVE,
        )
    )
    if record and _as_utc(record.expires_at) and _as_utc(record.expires_at) <= utcnow():
        expire_session(db, record)
        return None
    return record


def remaining_seconds(record: SessionRecord) -> int:
    expires_at = _as_utc(record.expires_at)
    if not expires_at:
        return 0
    return max(0, int((expires_at - utcnow()).total_seconds()))
