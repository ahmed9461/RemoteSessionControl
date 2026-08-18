# Windows connection methods

RemoteSessionControl intentionally supports multiple ways to start the **same temporary device client session**. These are not separate security models or separate remote-control systems. They all use the same Protocol v1, pairing rules, server-authoritative expiry, command allowlist, media handling, and audit path.

## Fixed rule

The server remains the authority for session lifetime regardless of the launch method. A 15-minute session still expires 15 minutes after first successful activation. Switching launch methods must never extend or bypass the session expiry.

## Method A — Portable one-file EXE (primary)

Artifact: `RemoteSessionControl-Client.exe`

Purpose:

- Simplest direct Windows package.
- No Python installation.
- No project checkout.
- No virtual environment.
- Same screenshot, screen-recording, device-info, status, and disconnect commands.

Example after HTTPS/WSS deployment:

```powershell
.\RemoteSessionControl-Client.exe --server https://control.example.com
```

The client asks for the one-time pairing code and explicit local consent before activation.

## Method B — PowerShell launcher (fallback / convenience)

Generic script: `scripts/windows/Start-RemoteSession.ps1`

The launcher does not implement remote control itself. It only starts the same visible temporary client. It can either:

1. use an already-downloaded EXE via `-ClientPath`, or
2. download the EXE over HTTPS via `-ClientUrl`.

When `-ExpectedSha256` is supplied, the client file is verified before execution.

The Telegram adapter also supports a **session-specific PowerShell launcher**. After a session is created and production HTTPS/client distribution are ready, pressing `⚡ PowerShell` makes the bot send a small `.ps1` file bound to that short-lived pairing code. The generated launcher:

- downloads the same EXE over HTTPS,
- reuses a previously downloaded copy only if its SHA-256 still matches,
- verifies SHA-256 before execution,
- starts the client as a separate visible process,
- lets the PowerShell launcher window close after startup,
- keeps the same server-side session expiry,
- installs no Windows service, Startup entry, scheduled task, or hidden persistence.

Generic local-file example:

```powershell
.\Start-RemoteSession.ps1 `
  -Server https://control.example.com `
  -ClientPath .\RemoteSessionControl-Client.exe
```

Generic download-and-verify example:

```powershell
.\Start-RemoteSession.ps1 `
  -Server https://control.example.com `
  -ClientUrl https://control.example.com/downloads/RemoteSessionControl-Client.exe `
  -ExpectedSha256 <published-sha256>
```

For remote servers, the launcher rejects plain HTTP. Plain HTTP is accepted only by the generic launcher for localhost testing.

## Method C — Portable runtime directory (fallback)

Artifact distributed as: `RemoteSessionControl-Windows-Portable.zip`

This is a PyInstaller `--onedir` package. It contains the client and its bundled runtime/dependencies in a directory. It exists as a compatibility fallback for systems where the single-file executable has extraction or startup issues.

Usage after extraction:

```powershell
.\RemoteSessionControl-Portable\RemoteSessionControl-Portable.exe --server https://control.example.com
```

It requires no separately installed Python environment.

## Telegram flow

Once `RSC_PUBLIC_BASE_URL` is HTTPS and the Windows artifacts are present in `RSC_DOWNLOADS_DIR`, creating a session can show:

```text
✅ تم إنشاء جلسة جديدة

🔑 مفتاح الربط: XXXXXXXX

[🪟 Windows EXE] [⚡ PowerShell]
[📦 Portable]
```

The EXE and Portable buttons point to the server's fixed allowlisted `/downloads/` files. The PowerShell button sends the session-specific launcher through Telegram. The pairing code is not stored inside the public repository or public client artifacts.

## Fallback order

Recommended order:

```text
Portable EXE
    ↓ if startup/runtime issue
PowerShell launcher
    ↓ if one-file packaging issue remains
Portable runtime directory
```

The user may choose any method directly. The fallback order is operational convenience only; it does not change privileges or session capabilities.

## Distribution design

The Windows CI build produces a complete artifact named:

```text
RemoteSessionControl-Windows-Distribution
```

It contains the Windows one-file client, SHA-256 file, generic PowerShell launcher, portable-runtime ZIP, and a build manifest. These deployment artifacts contain no Telegram token, owner key, reconnect token, or other server secret.

Production distribution is served by the VPS only after HTTPS/WSS is configured. See `docs/DEPLOYMENT.md`.

## Security boundaries

All three methods retain the project security boundaries:

- explicit local execution and consent,
- no arbitrary shell command,
- no credential collection,
- no antivirus/EDR bypass,
- no hidden persistence,
- no automatic startup,
- no session-expiry bypass,
- capture only through the allowlisted session commands.
