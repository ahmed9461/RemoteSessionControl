from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from core.commands import DISCONNECT, SESSION_STATUS, complete_command, create_command, mark_sent, queued_commands
from core.config import get_settings
from core.database import db_session, init_db
from core.identity import bootstrap_identities
from core.media import cleanup_expired_media, save_upload
from core.models import CommandRecord, Device, MediaRecord, SessionRecord
from core.security import constant_time_equal
from core.sessions import (
    ACTIVE,
    activate_with_pairing,
    create_session,
    expire_due_sessions,
    remaining_seconds,
    revoke_session,
    validate_reconnect_token,
)
from infrastructure.connection_manager import manager
from protocol import PROTOCOL_VERSION
from protocol.messages import command_envelope, error_envelope

settings = get_settings()


class SessionCreate(BaseModel):
    duration_seconds: int = Field(ge=60, le=86400)


class CommandCreate(BaseModel):
    command: str
    payload: dict = Field(default_factory=dict)


def owner_guard(x_owner_key: Annotated[str | None, Header()] = None) -> None:
    if settings.owner_api_key == "change-me":
        raise HTTPException(status_code=503, detail="RSC_OWNER_API_KEY must be configured")
    if not x_owner_key or not constant_time_equal(x_owner_key, settings.owner_api_key):
        raise HTTPException(status_code=401, detail="unauthorized")


def session_dict(row: SessionRecord) -> dict:
    return {
        "id": row.id,
        "device_id": row.device_id,
        "status": row.status,
        "requested_duration_seconds": row.requested_duration_seconds,
        "created_at": row.created_at,
        "activated_at": row.activated_at,
        "expires_at": row.expires_at,
        "remaining_seconds": remaining_seconds(row) if row.status == ACTIVE else 0,
        "disconnect_reason": row.disconnect_reason,
    }


def command_dict(row: CommandRecord) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "device_id": row.device_id,
        "command": row.name,
        "status": row.status,
        "result": json.loads(row.result_json or "{}"),
        "media_id": row.media_id,
        "error": row.error,
        "created_at": row.created_at,
        "completed_at": row.completed_at,
    }


async def maintenance_loop() -> None:
    while True:
        await asyncio.sleep(5)
        with db_session() as db:
            expired_devices = expire_due_sessions(db)
            cleanup_expired_media(db)
        for device_id in expired_devices:
            await manager.close_device(device_id, reason="session expired")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
    with db_session() as db:
        bootstrap_identities(db)
    task = asyncio.create_task(maintenance_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="RemoteSessionControl", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "protocol_version": PROTOCOL_VERSION}


@app.post("/api/v1/sessions", dependencies=[Depends(owner_guard)])
def api_create_session(body: SessionCreate) -> dict:
    with db_session() as db:
        row, pairing_code = create_session(db, body.duration_seconds)
        db.flush()
        return {"session": session_dict(row), "pairing_code": pairing_code, "pairing_ttl_seconds": settings.pairing_ttl_seconds}


@app.get("/api/v1/sessions", dependencies=[Depends(owner_guard)])
def api_list_sessions() -> list[dict]:
    with db_session() as db:
        rows = db.scalars(select(SessionRecord).order_by(SessionRecord.created_at.desc()).limit(50)).all()
        return [session_dict(row) for row in rows]


@app.get("/api/v1/sessions/{session_id}", dependencies=[Depends(owner_guard)])
def api_get_session(session_id: str) -> dict:
    with db_session() as db:
        row = db.get(SessionRecord, session_id)
        if row is None:
            raise HTTPException(404, "session not found")
        return session_dict(row)


@app.get("/api/v1/devices", dependencies=[Depends(owner_guard)])
def api_list_devices() -> list[dict]:
    with db_session() as db:
        rows = db.scalars(select(Device).order_by(Device.created_at.desc())).all()
        result = []
        for row in rows:
            session = db.get(SessionRecord, row.current_session_id) if row.current_session_id else None
            result.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "platform": row.platform,
                    "platform_version": row.platform_version,
                    "client_version": row.client_version,
                    "last_seen": row.last_seen,
                    "session": session_dict(session) if session else None,
                }
            )
        return result


@app.post("/api/v1/devices/{device_id}/commands", dependencies=[Depends(owner_guard)])
async def api_create_command(device_id: str, body: CommandCreate) -> dict:
    with db_session() as db:
        try:
            row = create_command(db, device_id, body.command, body.payload)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        if row.name == SESSION_STATUS:
            session = db.get(SessionRecord, row.session_id)
            complete_command(db, row.id, success=True, result={"session": session_dict(session) if session else None})
            db.flush()
            return command_dict(row)

        envelope = command_envelope(row)
        sent = await manager.send_json(device_id, envelope)
        if sent:
            mark_sent(db, row)
        db.flush()
        return command_dict(row)


@app.get("/api/v1/commands/{command_id}", dependencies=[Depends(owner_guard)])
def api_get_command(command_id: str) -> dict:
    with db_session() as db:
        row = db.get(CommandRecord, command_id)
        if row is None:
            raise HTTPException(404, "command not found")
        return command_dict(row)


@app.get("/api/v1/media/{media_id}", dependencies=[Depends(owner_guard)])
def api_get_media(media_id: str):
    with db_session() as db:
        row = db.get(MediaRecord, media_id)
        if row is None or not Path(row.path).exists():
            raise HTTPException(404, "media not found")
        return FileResponse(row.path, media_type=row.content_type, filename=row.filename)


@app.post("/api/v1/device/media/{command_id}")
async def api_device_media(
    command_id: str,
    file: Annotated[UploadFile, File()],
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    with db_session() as db:
        try:
            session = validate_reconnect_token(db, token)
        except ValueError as exc:
            raise HTTPException(401, str(exc)) from exc
        command = db.get(CommandRecord, command_id)
        if command is None or command.session_id != session.id:
            raise HTTPException(403, "command does not belong to active session")
        try:
            media = await save_upload(db, command_id, file)
        except ValueError as exc:
            raise HTTPException(413, str(exc)) from exc
        db.flush()
        return {"media_id": media.id}


@app.websocket("/ws/device")
async def device_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    device_id: str | None = None
    session_id: str | None = None
    try:
        hello = await asyncio.wait_for(websocket.receive_json(), timeout=20)
        if hello.get("type") != "hello" or hello.get("protocol_version") != PROTOCOL_VERSION:
            await websocket.send_json(error_envelope("bad_hello", "unsupported protocol or hello message"))
            await websocket.close(code=4400)
            return

        with db_session() as db:
            if hello.get("pairing_code"):
                try:
                    activation = activate_with_pairing(db, str(hello["pairing_code"]), hello.get("device") or {})
                except ValueError as exc:
                    await websocket.send_json(error_envelope("pairing_failed", str(exc)))
                    await websocket.close(code=4401)
                    return
                record = activation.session
                device_id = activation.device.id
                session_id = record.id
                reconnect_token = activation.reconnect_token
            elif hello.get("reconnect_token"):
                try:
                    record = validate_reconnect_token(db, str(hello["reconnect_token"]))
                except ValueError as exc:
                    await websocket.send_json(error_envelope("reconnect_failed", str(exc)))
                    await websocket.close(code=4401)
                    return
                if not record.device_id:
                    await websocket.close(code=4401)
                    return
                device_id = record.device_id
                session_id = record.id
                reconnect_token = str(hello["reconnect_token"])
                device = db.get(Device, device_id)
                if device:
                    device.last_seen = datetime.now(timezone.utc)
            else:
                await websocket.send_json(error_envelope("auth_required", "pairing_code or reconnect_token required"))
                await websocket.close(code=4401)
                return

            expires_at = record.expires_at
            pending_ids = [row.id for row in queued_commands(db, device_id)]

        await manager.connect(device_id, websocket)
        await websocket.send_json(
            {
                "protocol_version": PROTOCOL_VERSION,
                "type": "hello_ack",
                "device_id": device_id,
                "session_id": session_id,
                "reconnect_token": reconnect_token,
                "expires_at": expires_at.isoformat() if expires_at else None,
            }
        )

        for command_id in pending_ids:
            with db_session() as db:
                command = db.get(CommandRecord, command_id)
                if command is None or command.status != "queued":
                    continue
                envelope = command_envelope(command)
            if await manager.send_json(device_id, envelope):
                with db_session() as db:
                    current = db.get(CommandRecord, command_id)
                    if current:
                        mark_sent(db, current)

        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            if msg_type == "heartbeat":
                with db_session() as db:
                    session = validate_reconnect_token(db, reconnect_token)
                    if session.id != session_id:
                        raise ValueError("session mismatch")
                    device = db.get(Device, device_id)
                    if device:
                        device.last_seen = datetime.now(timezone.utc)
                await websocket.send_json({"protocol_version": PROTOCOL_VERSION, "type": "heartbeat_ack"})
                continue

            if msg_type == "command_result":
                command_id = str(message.get("command_id") or "")
                with db_session() as db:
                    row = db.get(CommandRecord, command_id)
                    if row is None or row.device_id != device_id or row.session_id != session_id:
                        continue
                    completed = complete_command(
                        db,
                        command_id,
                        success=bool(message.get("success")),
                        result=message.get("result") if isinstance(message.get("result"), dict) else {},
                        media_id=message.get("media_id"),
                        error=str(message.get("error"))[:2000] if message.get("error") else None,
                    )
                    should_disconnect = completed.name == DISCONNECT and completed.status == "completed"
                    if should_disconnect:
                        session = db.get(SessionRecord, session_id)
                        if session:
                            revoke_session(db, session)
                if should_disconnect:
                    await websocket.send_json({"protocol_version": PROTOCOL_VERSION, "type": "session_ended", "reason": "manual disconnect"})
                    await websocket.close(code=4000, reason="manual disconnect")
                    return

    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except ValueError as exc:
        try:
            await websocket.send_json(error_envelope("session_invalid", str(exc)))
            await websocket.close(code=4401)
        except Exception:
            pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if device_id:
            await manager.disconnect(device_id, websocket)
