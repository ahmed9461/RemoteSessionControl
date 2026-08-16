from __future__ import annotations

import json

from core.models import CommandRecord
from protocol import PROTOCOL_VERSION


def command_envelope(record: CommandRecord) -> dict:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "type": "command",
        "command_id": record.id,
        "command": record.name,
        "payload": json.loads(record.payload_json or "{}"),
    }


def error_envelope(code: str, message: str) -> dict:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "type": "error",
        "code": code,
        "message": message,
    }
