# RemoteSessionControl

RemoteSessionControl is a **consent-based, temporary remote-session platform**. Telegram is the first channel adapter; Windows and macOS clients connect to a central server through a versioned protocol.

The project is intentionally designed so that Telegram is **not** the core. A future WhatsApp, web, mobile, Discord, or REST adapter can reuse the same sessions, devices, commands, security, media, and expiry logic.

## MVP capabilities

- Temporary sessions with one-time pairing codes.
- Session duration starts at the **first successful device activation**, not when the pairing code is created.
- Server-authoritative expiry and manual revocation.
- Reconnect during the same active session without extending its expiry.
- Device information.
- Screenshot capture.
- Screen recording (1–120 seconds; Telegram currently requests 30 seconds).
- Session status.
- Manual disconnect.
- Telegram owner allowlist.
- Temporary media storage with automatic TTL cleanup.
- Audit events.
- Versioned device protocol (`v1`).
- CI tests and source ZIP artifacts.

## Explicit security boundaries

This project does **not** implement stealth, hidden persistence, arbitrary shell execution, credential collection, antivirus bypass, or silent capture. The temporary client asks for local consent before activating a session and remains visibly running while the session is active.

## Architecture

```text
Telegram ─────┐
              │
WhatsApp ─────┼── Channel Gateway / Adapters
  (future)    │
Web ──────────┘
                     │
                     ▼
               Command Router
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
     Sessions      Devices       Media
        │            │            │
        └────────────┼────────────┘
                     ▼
                  Security
                     │
                     ▼
              Protocol v1
                     │
                     ▼
            Windows / macOS client
```

See `docs/ARCHITECTURE.md` and `docs/PROJECT_MEMORY.md` for the fixed design decisions.

## Requirements

- Python 3.12+
- A server reachable by the device client.
- HTTPS/WSS in production.
- Telegram bot token for the Telegram adapter.
- On macOS, the user must grant the normal Screen Recording permission to the client process.

## Quick start

### 1. Create the environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure

Copy `.env.example` to `.env` and set at least:

- `RSC_OWNER_API_KEY` — a long random secret.
- `RSC_TELEGRAM_TOKEN` — BotFather token.
- `RSC_TELEGRAM_OWNER_IDS` — comma-separated Telegram user IDs allowed to use the bot.
- `RSC_SERVER_URL` — URL used by the Telegram adapter to reach the server.

Never commit `.env`.

### 3. Run the server

```bash
uvicorn apps.server.app:app --host 127.0.0.1 --port 8000
```

For Internet access, put it behind a TLS reverse proxy and expose HTTPS/WSS. Do not expose the development server directly without TLS.

### 4. Run Telegram adapter

```bash
python -m apps.telegram.bot
```

Use `/start`, choose **➕ جلسة جديدة**, and select a duration. The bot returns a one-time pairing code.

### 5. Run the temporary device client

```bash
python -m apps.device_client.main --server https://your-server.example
```

Enter the pairing code and explicitly confirm local consent. The session clock begins only after successful activation.

## Session timing example

If a two-hour session is created at 10:00 but the device activates at 11:30:

```text
created_at   = 10:00
activated_at = 11:30
expires_at   = 13:30
```

The pairing-code TTL is separate from the session duration.

## Tests

```bash
pytest -q
```

## Packaging

The GitHub Actions workflow `package-source.yml` runs tests and uploads `RemoteSessionControl-source.zip` as a workflow artifact. `build-device-clients.yml` can build visible consent-based Windows/macOS client executables via PyInstaller.

## Project status

Current version: `0.1.0` — MVP foundation.

See `docs/ROADMAP.md` for the next stages.
