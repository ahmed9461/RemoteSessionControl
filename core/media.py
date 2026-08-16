from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.models import MediaRecord


def media_root() -> Path:
    root = Path(get_settings().media_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_upload(db: Session, command_id: str, upload: UploadFile) -> MediaRecord:
    content_type = upload.content_type or "application/octet-stream"
    suffix = Path(upload.filename or "file.bin").suffix[:16]
    media_id = str(uuid4())
    filename = f"{media_id}{suffix}"
    path = media_root() / filename

    size = 0
    with path.open("wb") as handle:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > 100 * 1024 * 1024:
                handle.close()
                path.unlink(missing_ok=True)
                raise ValueError("media exceeds 100 MiB limit")
            handle.write(chunk)

    now = datetime.now(timezone.utc)
    record = MediaRecord(
        id=media_id,
        command_id=command_id,
        path=str(path),
        filename=upload.filename or filename,
        content_type=content_type,
        size=size,
        created_at=now,
        expires_at=now + timedelta(seconds=get_settings().media_ttl_seconds),
    )
    db.add(record)
    db.flush()
    return record


def cleanup_expired_media(db: Session) -> int:
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(MediaRecord)).all()
    deleted = 0
    for row in rows:
        expiry = row.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= now:
            Path(row.path).unlink(missing_ok=True)
            db.delete(row)
            deleted += 1
    return deleted
