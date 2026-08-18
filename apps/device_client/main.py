from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import platform
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
import mss
import mss.tools
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


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundled_ffmpeg() -> Path | None:
    """Return a bundled encoder when this platform build intentionally ships one.

    Windows production builds exclude imageio_ffmpeg from the core EXE and receive
    the encoder lazily as a verified component. macOS builds can still bundle it.
    """

    try:
        module = importlib.import_module("imageio_ffmpeg")
    except ImportError:
        return None
    try:
        path = Path(module.get_ffmpeg_exe())
    except Exception:
        return None
    return path if path.is_file() else None


def _component_cache_path() -> Path:
    root = Path(tempfile.gettempdir()) / "RemoteSessionControl"
    root.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    return root / f"RemoteSessionControl-FFmpeg{suffix}"


def _safe_component_url(url: str) -> bool:
    lowered = url.lower()
    return lowered.startswith("https://") or lowered.startswith("http://127.0.0.1") or lowered.startswith("http://localhost")


async def ensure_recording_encoder(component: dict | None) -> Path:
    component = component if isinstance(component, dict) else {}
    if component.get("available"):
        url = str(component.get("url") or "")
        expected = str(component.get("sha256") or "").strip().lower()
        if not _safe_component_url(url):
            raise RuntimeError("recording helper URL must use HTTPS")
        if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
            raise RuntimeError("recording helper metadata has an invalid SHA-256")

        target = _component_cache_path()
        if target.is_file() and _sha256_path(target) == expected:
            return target

        part = target.with_name(target.name + ".download")
        part.unlink(missing_ok=True)
        try:
            async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with part.open("wb") as handle:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            handle.write(chunk)
            actual = _sha256_path(part)
            if actual != expected:
                raise RuntimeError(f"recording helper SHA-256 mismatch: expected {expected}, got {actual}")
            os.replace(part, target)
            if os.name != "nt":
                target.chmod(0o700)
            return target
        finally:
            part.unlink(missing_ok=True)

    bundled = _bundled_ffmpeg()
    if bundled:
        return bundled
    raise RuntimeError("screen-recording encoder is not available for this client build")


def record_screen(path: Path, duration: int, fps: int, ffmpeg_path: Path) -> None:
    """Capture BGRA frames with MSS and pipe them directly into FFmpeg.

    This deliberately avoids NumPy and ImageIO in the core client. On Windows the
    FFmpeg executable is a separately verified, lazy-loaded helper so normal
    pairing/screenshot/device-info sessions do not carry the encoder in the EXE.
    """

    duration = min(120, max(1, int(duration)))
    fps = min(10, max(2, int(fps)))
    interval = 1.0 / fps

    with mss.mss() as sct:
        monitor = sct.monitors[0]
        width = int(monitor["width"])
        height = int(monitor["height"])
        command = [
            str(ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pixel_format",
            "bgra",
            "-video_size",
            f"{width}x{height}",
            "-framerate",
            str(fps),
            "-i",
            "pipe:0",
            "-an",
            "-vf",
            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "26",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(path),
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        if process.stdin is None or process.stderr is None:
            process.kill()
            raise RuntimeError("failed to start the screen-recording encoder")

        capture_error: Exception | None = None
        try:
            started = time.perf_counter()
            for frame_index in range(duration * fps):
                target = started + frame_index * interval
                delay = target - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                shot = sct.grab(monitor)
                process.stdin.write(shot.bgra)
        except Exception as exc:
            capture_error = exc
        finally:
            try:
                process.stdin.close()
            except Exception:
                pass

        stderr = process.stderr.read().decode("utf-8", errors="replace")[-2000:]
        return_code = process.wait()
        if capture_error is not None:
            raise RuntimeError(f"screen capture failed: {capture_error}") from capture_error
        if return_code != 0:
            raise RuntimeError(f"FFmpeg exited with code {return_code}: {stderr.strip()}")
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("screen recorder produced an empty video")


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


async def run_command(
    server_url: str,
    reconnect_token: str,
    message: dict,
    components: dict | None = None,
) -> tuple[dict, bool]:
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
            component_map = components if isinstance(components, dict) else {}
            ffmpeg_path = await ensure_recording_encoder(component_map.get("screen_recorder"))
            with tempfile.TemporaryDirectory(prefix="rsc-") as tmp:
                path = Path(tmp) / "screen.mp4"
                await asyncio.to_thread(record_screen, path, duration, fps, ffmpeg_path)
                media_id = await upload_media(server_url, reconnect_token, command_id, path, "video/mp4")
            return (
                {
                    "type": "command_result",
                    "command_id": command_id,
                    "success": True,
                    "media_id": media_id,
                    "result": {"duration": duration, "fps": fps},
                },
                True,
            )

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
                components = ack.get("components") if isinstance(ack.get("components"), dict) else {}
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
                        result, keep_running = await run_command(server_url, reconnect_token, message, components)
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
    parser.add_argument("--server", help="Server base URL, e.g. https://example.com")
    parser.add_argument("--pairing-code", help="One-time pairing code. Omit to be prompted.")
    parser.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        print(f"RemoteSessionControl client {CLIENT_VERSION} self-test OK")
        print(f"Protocol version: {PROTOCOL_VERSION}")
        print(f"Platform: {platform.system()} {platform.machine()}")
        return
    if not args.server:
        raise SystemExit("--server is required")

    pairing_code = args.pairing_code or input("Pairing code: ").strip().upper()
    print("RemoteSessionControl will allow approved screen capture and device-info commands during this temporary session.")
    consent = input("Continue and activate the temporary session? [y/N]: ").strip().lower()
    if consent not in {"y", "yes"}:
        print("Cancelled.")
        return
    asyncio.run(client_loop(args.server, pairing_code))


if __name__ == "__main__":
    main()
