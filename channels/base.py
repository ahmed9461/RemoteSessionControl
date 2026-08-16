from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChannelContext:
    channel: str
    external_user_id: str
    conversation_id: str


@dataclass(frozen=True, slots=True)
class RoutedCommand:
    command: str
    device_id: str
    payload: dict
    origin: ChannelContext


class ChannelAdapter(Protocol):
    """Minimal contract every future messaging integration should implement."""

    name: str

    async def send_text(self, context: ChannelContext, text: str) -> None: ...

    async def send_media(self, context: ChannelContext, data: bytes, content_type: str) -> None: ...
