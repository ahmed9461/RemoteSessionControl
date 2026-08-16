from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import socket
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
import imageio.v2 as imageio
import mss
import mss.tools
import numpy as np
import psutil
import websockets

from protocol import PROTOCOL_VERSION

CLIENT_VERSION = "0.1.0"


def instance_id_path() -> Path:
    return Path.home() / ".remote_session_control" / "device_id"


def load_or_create_instance_id() -> str:
    path = instance_id_path()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    path.parent.mkdir(parents=True, exist_ok=True)
    value = str(uuid4())
    path.write_text(value, encoding="utf-8")
    if os.name != "nt":
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return value


def device_info() -> dict:
    return {
        "instance_id": load_or_create_instance_id(),
        "name": socket.gethostname(),
        "platform": platform.system(),
        "platform_version": platform.version(),
        "client_version": CLIENT_VERSION,
    }


def detailed_info() -> dict:
    vm = psutil.virtual_memory()
    return {
        **device_info(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": psutil.cpu_count(),
        "memory_total_bytes": vm.total,
        "memory_available_bytes": vm.available,
    }


def websocket_url(server_url: str) -> str:
    base = server_url.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base.removeprefix("https://") + "/ws/device"
    if base.startswith("http://"):
        return "ws://" + base.removeprefix("http://") + "/ws/device"
    raise ValueError("server URL must start with http:// or https://")


def capture_screenshot(path: Path) -> None:
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))


def record_screen(path: Path, duration: int, fps: int) -> None:
    duration = min(120, max(1, int(duration)))
    fps = min(10, max(2, int(fps)))
    interval = 1.0 / fps
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        writer = imageio.get_writer(str(path), fps=fps, codec="libx264", quality=6, macro_block_size=2)
        try:
            started = time.perf_counter()
            for frame_index in range(duration * fps):
                target = started + frame_index * interval
                delay = target - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                frame = np.asarray(sct.grab(monitor))[:, :, :3]
                frame = frame[:, :, ::-1]
                writer.append_data(frame)
        finally:
            writer.close()


async def upload_media(server_url: str, reconnect_token: str, command_id: str, path: Path, content_type: str) -> str:
    headers = {"Authorization": f"Bearer {reconnect_token}"}
    async with httpx.AsyncClient(timeout=180) as client:
        with path.open("rb") as handle:
            response = await client.post(
                f"{server_url.rstrip('/')}/api/v1/device/media/{command_id}",
                headers=headers,
                files={"file": (path.name, handle, content_type)},
            )
        response.raise_for_status()
        return response.json()["media_id"]


async def run_command(server_url: str, reconnect_token: str, message: dict) -> tuple[dict, bool]:
    command_id = str(message.get("command_id"))
    command = message.get("command")
    payload = message.get("payload") or {}
    try:
        if command == "DEVICE_INFO":
            return ({"type": "command_result", "command_id": command_id, "success": True, "result": detailed_info()}, True)

        if command == "SCREENSHOT":
            with tempfile.TemporaryDirectory(prefix="rsc-") as tmp:
                path = Path(tmp) / "screenshot.png"
                await asyncio.to_thread(capture_screenshot, path)
                media_id = await upload_media(server_url, reconnect_token, command_id, path, "image/png")
            return ({"type": "command_result", "command_id": command_id, "success": True, "media_id": media_id, "result": {}}, True)

        if command == "RECORD_SCREEN":
            duration = min(120, max(1, int(payload.get("duration", 30))))
            fps = min(10, max(2, int(payload.get("fps", 5))))
            with tempfile.TemporaryDirectory(prefix="rsc-") as tmp:
                path = Path(tmp) / "screen.mp4"
                await asyncio.to_thread(record_screen, path, duration, fps)
                media_id = await upload_media(server_url, reconnect_token, command_id, path, "video/mp4")
            return ({"type": "command_result", "command_id": command_id, "success": True, "media_id": media_id, "result": {"duration": duration, "fps": fps}}, True)

        if command == "DISCONNECT":
            return ({"type": "command_result", "command_id": command_id, "success": True, "result": {"disconnected": True}}, False)

        return ({"type": "command_result", "command_id": command_id, "success": False, "error": "unsupported command"}, True)
    except Exception as exc:
        return ({"type": "command_result", "command_id": command_id, "success": False, "error": f"{type(exc).__name__}: {exc}"}, True)


async def client_loop(server_url: str, pairing_code: str) -> None:
    reconnect_token: str | None = None
    keep_running = True
    while keep_running:
        hello = {"protocol_version": PROTOCOL_VERSION, "type": "hello", "device": device_info()}
        if reconnect_token:
            hello["reconnect_token"] = reconnect_token
        else:
            hello["pairing_code"] = pairing_code

        try:
            async with websockets.connect(websocket_url(server_url), max_size=2 * 1024 * 1024) as ws:
                await ws.send(json.dumps(hello))
                ack = json.loads(await ws.recv())
                if ack.get("type") == "error":
                    raise RuntimeError(ack.get("message", "connection rejected"))
                if ack.get("type") != "hello_ack":
                    raise RuntimeError("unexpected server response")
                reconnect_token = ack["reconnect_token"]
                print(f"Session active for device {ack['device_id']} until {ack.get('expires_at')}")
                print("This client is visible and consent-based. Screen capture occurs only while this session is active.")

                async def heartbeat() -> None:
                    while True:
                        await asyncio.sleep(20)
                        await ws.send(json.dumps({"protocol_version": PROTOCOL_VERSION, "type": "heartbeat"}))

                heartbeat_task = asyncio.create_task(heartbeat())
                try:
                    async for raw in ws:
                        message = json.loads(raw)
                        if message.get("type") == "session_ended":
                            print(f"Session ended: {message.get('reason')}")
                            keep_running = False
                            break
                        if message.get("type") == "error" and message.get("code") == "session_invalid":
                            print(f"Session ended: {message.get('message')}")
                            keep_running = False
                            break
                        if message.get("type") != "command":
                            continue
                        result, keep_running = await run_command(server_url, reconnect_token, message)
                        result["protocol_version"] = PROTOCOL_VERSION
                        await ws.send(json.dumps(result))
                        if not keep_running:
                            break
                finally:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
        except KeyboardInterrupt:
            return
        except Exception as exc:
            if not reconnect_token:
                raise
            print(f"Connection lost ({exc}); retrying in 3 seconds while the same session is valid...")
            await asyncio.sleep(3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RemoteSessionControl temporary device client")
    parser.add_argument("--server", required=True, help="Server base URL, e.g. https://example.com")
    parser.add_argument("--pairing-code", help="One-time pairing code. Omit to be prompted.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pairing_code = args.pairing_code or input("Pairing code: ").strip().upper()
    print("RemoteSessionControl will allow approved screen capture and device-info commands during this temporary session.")
    consent = input("Continue and activate the temporary session? [y/N]: ").strip().lower()
    if consent not in {"y", "yes"}:
        print("Cancelled.")
        return
    asyncio.run(client_loop(args.server, pairing_code))


if __name__ == "__main__":
    main()
