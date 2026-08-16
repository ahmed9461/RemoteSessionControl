from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.models import ChannelIdentity, Owner

PRIMARY_OWNER_ID = "primary-owner"


def bootstrap_identities(db: Session) -> None:
    owner = db.get(Owner, PRIMARY_OWNER_ID)
    if owner is None:
        db.add(Owner(id=PRIMARY_OWNER_ID, display_name="Owner"))
        db.flush()

    for telegram_id in get_settings().owner_telegram_ids:
        external_id = str(telegram_id)
        existing = db.scalar(
            select(ChannelIdentity).where(
                ChannelIdentity.channel == "telegram",
                ChannelIdentity.external_id == external_id,
            )
        )
        if existing is None:
            db.add(
                ChannelIdentity(
                    id=str(uuid4()),
                    owner_id=PRIMARY_OWNER_ID,
                    channel="telegram",
                    external_id=external_id,
                    enabled=True,
                )
            )


def identity_enabled(db: Session, channel: str, external_id: str) -> bool:
    row = db.scalar(
        select(ChannelIdentity).where(
            ChannelIdentity.channel == channel,
            ChannelIdentity.external_id == external_id,
            ChannelIdentity.enabled.is_(True),
        )
    )
    return row is not None
