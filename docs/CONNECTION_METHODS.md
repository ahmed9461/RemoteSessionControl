# Windows connection methods

RemoteSessionControl intentionally supports multiple ways to start the **same temporary device client session**. These are not separate security models or separate remote-control systems. They all use the same Protocol v1, pairing rules, server-authoritative expiry, command allowlist, media handling, and audit path.

## Fixed rule

The server remains the authority for session lifetime regardless of launch method. A 15-minute session still expires 15 minutes after first successful activation. Switching launch methods never extends or bypasses the session expiry.

## Method A — One-click BAT (recommended)

Generated per session by Telegram: `Start-RemoteSession-<PAIRING>.bat`

The BAT launcher is the preferred owner-operated Windows flow. The user downloads the small session file and double-clicks it. It:

- uses normal Windows `cmd.exe`,
- downloads the same core EXE with `curl.exe`,
- verifies SHA-256 with `certutil.exe`,
- reuses the cached client only when its hash matches,
- starts the EXE with the HTTPS server URL and one-time pairing code already supplied,
- still leaves the client's explicit local consent prompt in place,
- changes no PowerShell Execution Policy,
- installs no service, Startup entry, scheduled task, or persistence.

## Method B — One-click CMD PowerShell compatibility launcher

Generated per session by Telegram: `Start-RemoteSession-<PAIRING>.cmd`

This is a separate fallback for systems where the PowerShell script itself is blocked by an `AllSigned`/`RemoteSigned` policy. The CMD file:

1. downloads the published generic PowerShell launcher,
2. verifies its SHA-256,
3. runs it with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...`,
4. applies that Bypass only to that child PowerShell process.

It does **not** run `Set-ExecutionPolicy` and does not alter machine/user policy persistently.

## Method C — Portable one-file EXE

Artifact: `RemoteSessionControl-Client.exe`

Purpose:

- direct Windows package,
- no Python installation,
- no project checkout,
- no virtual environment,
- same screenshot, recording, device-info, status, and disconnect commands.

Example:

```powershell
.\RemoteSessionControl-Client.exe --server https://control.example.com
```

The client asks for the one-time pairing code and explicit local consent before activation.

### Lightweight recorder design

The Windows one-file EXE intentionally does **not** carry FFmpeg, NumPy, ImageIO, or Pillow in its normal capture path.

- Screenshots use MSS directly.
- Device info, pairing, heartbeats, and disconnect need no video stack.
- FFmpeg is required only when `RECORD_SCREEN` must turn captured raw frames into H.264/MP4.
- The Windows build publishes `RemoteSessionControl-FFmpeg.exe` separately.
- On the first video request, the client reads the public non-secret `manifest.json`, obtains the published recorder SHA-256, downloads the helper over the same HTTPS server, verifies it, and caches it under the OS temporary directory.
- Later recordings reuse that helper only while its SHA-256 remains correct.

This keeps normal startup/download lighter while preserving MP4 recording.

## Method D — PowerShell launcher

Generic script: `scripts/windows/Start-RemoteSession.ps1`

The launcher does not implement remote control itself. It only starts the same visible temporary client. It can use an existing EXE or download/verify the EXE over HTTPS. The Telegram adapter can generate a session-specific PS1 as well.

If the machine's PowerShell Execution Policy blocks the PS1, use the one-click BAT or CMD options instead of permanently changing the system policy.

## Method E — Portable runtime directory

Artifact: `RemoteSessionControl-Windows-Portable.zip`

This is a PyInstaller `--onedir` fallback. The Windows build includes the recording helper inside this portable package so recording can remain self-contained in the fallback distribution.

It requires no separately installed Python environment.

## Telegram flow

Once HTTPS and Windows artifacts are ready, a new session can show:

```text
✅ تم إنشاء جلسة جديدة

🔑 مفتاح الربط: XXXXX-XXXX

[🚀 BAT سريع] [🧩 CMD تلقائي]
[🪟 Windows EXE] [⚡ PowerShell]
[📦 Portable]
```

Recommended order:

```text
BAT one-click
    ↓ if CMD/tool compatibility issue
CMD automatic PowerShell fallback
    ↓
Direct EXE / PowerShell / Portable as needed
```

The fallback order is operational convenience only. It does not change privileges, commands, local consent, or session capabilities.

## Distribution design

The Windows CI build produces `RemoteSessionControl-Windows-Distribution` containing:

```text
RemoteSessionControl-Client.exe
RemoteSessionControl-Client.exe.sha256
RemoteSessionControl-FFmpeg.exe
RemoteSessionControl-Windows-Portable.zip
Start-RemoteSession.ps1
manifest.json
```

The build manifest contains version/source SHA and file hashes only. It contains no Telegram token, owner API key, reconnect token, pairing code, or other server secret.

## Security boundaries

All methods retain the project security boundaries:

- explicit local execution and consent,
- no arbitrary shell command exposed through the device protocol,
- no credential collection,
- no antivirus/EDR bypass,
- no hidden persistence,
- no automatic startup,
- no session-expiry bypass,
- capture only through allowlisted session commands.
