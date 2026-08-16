from __future__ import annotations

import json

from sqlalchemy.orm import Session

from core.models import AuditLog


def audit(
    db: Session,
    event: str,
    *,
    session_id: str | None = None,
    device_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            event=event,
            session_id=session_id,
            device_id=device_id,
            details=json.dumps(details or {}, ensure_ascii=False),
        )
    )
