from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.audit import audit
from core.models import CommandRecord
from core.sessions import active_session_for_device

DEVICE_INFO = "DEVICE_INFO"
SCREENSHOT = "SCREENSHOT"
RECORD_SCREEN = "RECORD_SCREEN"
SESSION_STATUS = "SESSION_STATUS"
DISCONNECT = "DISCONNECT"
ALLOWED_COMMANDS = {DEVICE_INFO, SCREENSHOT, RECORD_SCREEN, SESSION_STATUS, DISCONNECT}


def create_command(db: Session, device_id: str, name: str, payload: dict | None = None) -> CommandRecord:
    if name not in ALLOWED_COMMANDS:
        raise ValueError("unsupported command")
    session = active_session_for_device(db, device_id)
    if session is None:
        raise ValueError("device has no active session")

    payload = payload or {}
    if name == RECORD_SCREEN:
        duration = int(payload.get("duration", 30))
        if duration < 1 or duration > 120:
            raise ValueError("recording duration must be between 1 and 120 seconds")
        payload = {"duration": duration, "fps": min(10, max(2, int(payload.get("fps", 5))))}

    record = CommandRecord(
        id=str(uuid4()),
        session_id=session.id,
        device_id=device_id,
        name=name,
        payload_json=json.dumps(payload),
        status="queued",
    )
    db.add(record)
    db.flush()
    audit(db, "command_created", session_id=session.id, device_id=device_id, details={"command": name})
    return record


def queued_commands(db: Session, device_id: str) -> list[CommandRecord]:
    return list(
        db.scalars(
            select(CommandRecord)
            .where(CommandRecord.device_id == device_id, CommandRecord.status == "queued")
            .order_by(CommandRecord.created_at.asc())
        ).all()
    )


def mark_sent(db: Session, record: CommandRecord) -> None:
    if record.status == "queued":
        record.status = "sent"


def complete_command(
    db: Session,
    command_id: str,
    *,
    success: bool,
    result: dict | None = None,
    media_id: str | None = None,
    error: str | None = None,
) -> CommandRecord:
    record = db.get(CommandRecord, command_id)
    if record is None:
        raise ValueError("unknown command")
    if record.status in {"completed", "failed"}:
        return record
    record.status = "completed" if success else "failed"
    record.result_json = json.dumps(result or {}, ensure_ascii=False)
    record.media_id = media_id
    record.error = error
    record.completed_at = datetime.now(timezone.utc)
    audit(
        db,
        "command_completed" if success else "command_failed",
        session_id=record.session_id,
        device_id=record.device_id,
        details={"command": record.name, "error": error},
    )
    return record
