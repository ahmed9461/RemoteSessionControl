from __future__ import annotations

import pytest

from core.commands import RECORD_SCREEN, SCREENSHOT, create_command
from core.sessions import activate_with_pairing, create_session


def active_device(db) -> str:
    _, code = create_session(db, 600)
    activation = activate_with_pairing(db, code, {"instance_id": "command-device", "name": "PC", "platform": "Windows"})
    return activation.device.id


def test_supported_command_created(db):
    device_id = active_device(db)
    command = create_command(db, device_id, SCREENSHOT)
    assert command.status == "queued"
    assert command.name == SCREENSHOT


def test_recording_duration_is_bounded(db):
    device_id = active_device(db)
    with pytest.raises(ValueError, match="between 1 and 120"):
        create_command(db, device_id, RECORD_SCREEN, {"duration": 121})


def test_unknown_command_rejected(db):
    device_id = active_device(db)
    with pytest.raises(ValueError, match="unsupported command"):
        create_command(db, device_id, "SHELL", {"command": "whoami"})
