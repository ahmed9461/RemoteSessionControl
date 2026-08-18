# VPS deployment

This document describes the production shape for the current MVP. The FastAPI process remains bound to `127.0.0.1:8000`; Caddy exposes HTTPS/WSS publicly and proxies to it.

## 1. Environment

Use `/opt/RemoteSessionControl/.env` and keep it out of Git.

Minimum production values:

```env
RSC_OWNER_API_KEY=<long-random-secret>
RSC_DATABASE_URL=sqlite:///./data/app.db
RSC_PUBLIC_BASE_URL=https://control.example.com
RSC_SERVER_URL=http://127.0.0.1:8000
RSC_MEDIA_DIR=data/media
RSC_DOWNLOADS_DIR=data/downloads
RSC_MEDIA_TTL_SECONDS=600
RSC_PAIRING_TTL_SECONDS=600
RSC_TELEGRAM_TOKEN=<telegram-token>
RSC_TELEGRAM_OWNER_IDS=<telegram-user-id>
```

`RSC_SERVER_URL` stays local because the Telegram adapter runs on the same VPS. `RSC_PUBLIC_BASE_URL` is the external HTTPS URL used by Windows clients and download links.

## 2. systemd

Copy the supplied units:

```bash
cp deploy/systemd/rsc-server.service /etc/systemd/system/
cp deploy/systemd/rsc-telegram.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now rsc-server rsc-telegram
```

Check:

```bash
systemctl status rsc-server rsc-telegram --no-pager
curl http://127.0.0.1:8000/health
```

## 3. HTTPS/WSS with Caddy

Point a DNS name such as `control.example.com` to the VPS first. Install Caddy from its official package repository, then copy/adapt `deploy/Caddyfile.example` to `/etc/caddy/Caddyfile`.

The intended proxy is:

```text
Internet HTTPS/WSS
        ↓
      Caddy
        ↓
127.0.0.1:8000
        ↓
     FastAPI
```

Do not bind Uvicorn directly to a public interface for production.

After Caddy is active, verify:

```bash
curl https://control.example.com/health
```

The device client automatically converts an `https://` server URL to `wss://.../ws/device` for its control channel.

## 4. Publish Windows client artifacts

The GitHub Actions workflow `Build visible device clients` produces a complete artifact named:

```text
RemoteSessionControl-Windows-Distribution
```

It contains:

```text
RemoteSessionControl-Client.exe
RemoteSessionControl-Client.exe.sha256
RemoteSessionControl-Windows-Portable.zip
Start-RemoteSession.ps1
manifest.json
```

Copy the distribution files into:

```text
/opt/RemoteSessionControl/data/downloads/
```

Recommended permissions:

```bash
mkdir -p /opt/RemoteSessionControl/data/downloads
chmod 755 /opt/RemoteSessionControl/data/downloads
chmod 644 /opt/RemoteSessionControl/data/downloads/*
```

The server exposes only the fixed allowlisted client artifact names beneath `/downloads/`; arbitrary paths are rejected.

## 5. Telegram connection methods

Once both conditions are true:

1. `RSC_PUBLIC_BASE_URL` starts with `https://`.
2. Windows artifacts are present in `data/downloads`.

A newly-created Telegram session can expose:

- `🪟 Windows EXE`
- `⚡ PowerShell`
- `📦 Portable`

The PowerShell button generates a session-specific launcher in Telegram. It contains that session's short-lived pairing code, downloads the same EXE over HTTPS, verifies its SHA-256, and starts the visible client. It does not install a service, Startup entry, scheduled task, or hidden persistence.

## 6. Security invariants

- Pairing-code lifetime and active-session lifetime remain separate.
- The active-session timer begins only on first successful device activation.
- Server-side expiry remains authoritative for all launch methods.
- Download artifacts contain no Telegram token, owner API key, reconnect token, or other server secret.
- The client command set remains allowlisted; no arbitrary shell is exposed.
- HTTPS/WSS is required for remote production use.
